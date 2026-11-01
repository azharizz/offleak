use gpui::{div, prelude::*, px, rgb, size, App, Application, Bounds, Context, Window, WindowBounds, WindowOptions};

struct Prototype;
impl Render for Prototype {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        div().size_full().bg(rgb(0x121820)).text_color(rgb(0xe8edf4)).p_6().flex().flex_col().gap_4()
            .child(div().text_xl().child("Offleak · GPUI experiment"))
            .child("Interface proof of concept")
            .child("This window does not control OBS or run protection.")
            .child("Use the existing Offleak application for the working demo.")
    }
}
fn main() {
    Application::new().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(500.), px(220.)), cx);
        cx.open_window(WindowOptions { window_bounds: Some(WindowBounds::Windowed(bounds)), ..Default::default() },
            |_, cx| cx.new(|_| Prototype)).unwrap();
        cx.activate(true);
    });
}
