#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod mdns_discovery;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![mdns_discovery::discover_lovely_pos_servers])
        .run(tauri::generate_context!())
        .expect("error while running Lovely Tech POS");
}