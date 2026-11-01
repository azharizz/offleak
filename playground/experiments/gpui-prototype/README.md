# GPUI window experiment

This is a standalone static window, not an Offleak or OBS integration. It does not process video, manage settings, or provide privacy protection. It exists to check whether the selected GPUI dependency can build and open locally; it is not a comparable GUI performance benchmark.

```sh
cargo run --release --locked --manifest-path playground/experiments/gpui-prototype/Cargo.toml
```

The existing application remains the working demo. The attempted build on this Mac failed because `xcrun` could not find the `metal` shader compiler with the installed Command Line Tools. An Xcode installation with the Metal toolchain is needed before building or testing this window here. Windows behavior and packaging require testing on Windows.
