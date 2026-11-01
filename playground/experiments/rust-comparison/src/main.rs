use ndarray::Array4;
use ort::{session::Session, value::Tensor};
use std::{env, fs, time::Instant};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    if !(7..=9).contains(&args.len()) { return Err("usage: rust MODEL INPUT SIZE WARMUP RUNS OUTPUT [THREADS [coreml]]".into()); }
    let size: usize = args[3].parse()?;
    let warmup: usize = args[4].parse()?;
    let runs: usize = args[5].parse()?;
    let threads: usize = if args.len() >= 8 { args[7].parse()? } else { 2 };
    if threads == 0 { return Err("threads must be positive".into()); }
    let bytes = fs::read(&args[2])?;
    let data: Vec<f32> = bytes.chunks_exact(4).map(|v| f32::from_le_bytes([v[0],v[1],v[2],v[3]])).collect();
    let count = 3 * size * size;
    if data.is_empty() || data.len() % count != 0 { return Err("invalid input tensor file".into()); }
    let inputs: Vec<_> = data.chunks_exact(count)
        .map(|chunk| Tensor::from_array(Array4::from_shape_vec((1, 3, size, size), chunk.to_vec()).unwrap()).unwrap())
        .collect();
    let mut builder = Session::builder()?.with_intra_threads(threads)?.with_inter_threads(1)?;
    if args.len() == 9 {
        if args[8] != "coreml" { return Err("unknown execution provider".into()); }
        let provider = ort::ep::CoreML::default()
            .with_model_format(ort::ep::coreml::ModelFormat::MLProgram)
            .with_compute_units(ort::ep::coreml::ComputeUnits::All)
            .with_static_input_shapes(true).build().error_on_failure();
        builder = builder.with_execution_providers([provider])?;
    }
    let mut session = builder.commit_from_file(&args[1])?;
    for i in 0..warmup { let _ = session.run(ort::inputs![&inputs[i % inputs.len()]])?; }
    let mut timings = Vec::new();
    for i in 0..runs {
        let start = Instant::now();
        let outputs = session.run(ort::inputs![&inputs[i % inputs.len()]])?;
        timings.push(start.elapsed().as_secs_f64() * 1000.0);
        std::hint::black_box(&outputs);
    }
    let mut out = Vec::new();
    for input in &inputs {
        let outputs = session.run(ort::inputs![input])?;
        for (_, value) in outputs.iter() {
            let (_, v) = value.try_extract_tensor::<f32>()?;
            for f in v { out.extend_from_slice(&f.to_le_bytes()); }
        }
    }
    fs::write(&args[6], out)?;
    println!("{}", serde_json::to_string(&timings)?);
    Ok(())
}
