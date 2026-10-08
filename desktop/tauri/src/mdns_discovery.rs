//! mDNS service discovery for Lovely Tech POS LAN server discovery.

use mdns_sd::{ServiceDaemon, ServiceEvent, ServiceInfo};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::Duration;
use tauri::command;

const SERVICE_TYPE: &str = "_lovely-tech-pos._tcp.local.";
const DISCOVERY_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveredServer {
    pub service_name: String,
    pub hostname: String,
    pub addresses: Vec<String>,
    pub port: u16,
    pub txt_records: HashMap<String, String>,
}

#[command]
pub async fn discover_lovely_pos_servers() -> Result<Vec<DiscoveredServer>, String> {
    let daemon = ServiceDaemon::new().map_err(|e| format!("Failed to create mDNS daemon: {}", e))?;

    let receiver = daemon.browse(SERVICE_TYPE).map_err(|e| format!("Failed to browse services: {}", e))?;

    let mut discovered = Vec::new();
    let start = std::time::Instant::now();

    while start.elapsed() < DISCOVERY_TIMEOUT {
        match receiver.recv_timeout(Duration::from_millis(500)) {
            Ok(ServiceEvent::ServiceResolved(info)) => {
                if let Some(server) = parse_service_info(info) {
                    discovered.push(server);
                }
            }
            Ok(ServiceEvent::ServiceFound(_, _)) => {
                // Service found but not yet resolved; wait for resolution
            }
            Ok(ServiceEvent::ServiceRemoved(_, _)) => {
                // Service removed; ignore
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                // Continue waiting
            }
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                break;
            }
        }
    }

    daemon.shutdown().map_err(|e| format!("Failed to shutdown mDNS daemon: {}", e))?;

    Ok(discovered)
}

fn parse_service_info(info: ServiceInfo) -> Option<DiscoveredServer> {
    let hostname = info.get_hostname().to_string();
    let port = info.get_port();
    let addresses: Vec<String> = info
        .get_addresses()
        .iter()
        .map(|addr| addr.to_string())
        .collect();

    let mut txt_records = HashMap::new();
    for (key, val) in info.get_properties().iter() {
        if let Ok(val_str) = std::str::from_utf8(val.val) {
            txt_records.insert(key.clone(), val_str.to_string());
        }
    }

    // Only include services that have the required identity fields
    if txt_records.contains_key("product") && txt_records.contains_key("instance_id") {
        Some(DiscoveredServer {
            service_name: info.get_fullname().to_string(),
            hostname,
            addresses,
            port,
            txt_records,
        })
    } else {
        None
    }
}