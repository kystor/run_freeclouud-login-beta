import base64
import json
import os
import sys
from urllib.parse import parse_qs, unquote, urlsplit


def fail(message: str) -> None:
    print(f"ERROR: {message}", flush=True)
    raise SystemExit(1)


def decode_b64_urlsafe(value: str) -> str:
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")


def get_first(mapping: dict, key: str, default: str = "") -> str:
    value = mapping.get(key, [default])[0]
    if value is None:
        return default
    return unquote(str(value))


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.replace("|", ",").split(",") if item.strip()]


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def add_tls_settings(stream_settings: dict, host: str, query: dict) -> None:
    security = get_first(query, "security", "none").lower()
    if security not in {"tls", "reality"}:
        return

    stream_settings["security"] = security
    server_name = get_first(query, "sni") or get_first(query, "serverName") or host

    if security == "tls":
        tls_settings = {"serverName": server_name}
        fingerprint = get_first(query, "fp") or get_first(query, "fingerprint")
        if fingerprint:
            tls_settings["fingerprint"] = fingerprint

        alpn = split_csv(get_first(query, "alpn"))
        if alpn:
            tls_settings["alpn"] = alpn

        insecure_value = get_first(query, "allowInsecure") or get_first(query, "insecure")
        if insecure_value:
            tls_settings["allowInsecure"] = truthy(insecure_value)

        stream_settings["tlsSettings"] = tls_settings
        return

    reality_settings = {
        "serverName": server_name,
        "publicKey": get_first(query, "pbk"),
        "shortId": get_first(query, "sid"),
        "fingerprint": get_first(query, "fp", "chrome") or "chrome",
    }
    spider_x = get_first(query, "spx")
    if spider_x:
        reality_settings["spiderX"] = spider_x
    stream_settings["realitySettings"] = reality_settings


def apply_tcp_settings(stream_settings: dict, query: dict) -> None:
    header_type = (get_first(query, "headerType") or get_first(query, "type")).lower()
    if header_type != "http":
        return

    host_header = split_csv(get_first(query, "host"))
    path = get_first(query, "path", "/") or "/"
    stream_settings["tcpSettings"] = {
        "header": {
            "type": "http",
            "request": {
                "path": [path],
                "headers": {"Host": host_header} if host_header else {},
            },
        }
    }


def apply_ws_settings(stream_settings: dict, query: dict) -> None:
    path = get_first(query, "path", "/") or "/"
    host = get_first(query, "host")
    ws_settings = {"path": path}
    if host:
        ws_settings["headers"] = {"Host": host}
    stream_settings["wsSettings"] = ws_settings


def apply_grpc_settings(stream_settings: dict, query: dict) -> None:
    service_name = get_first(query, "serviceName") or get_first(query, "path")
    grpc_settings = {"serviceName": service_name}

    mode = get_first(query, "mode")
    if mode:
        grpc_settings["multiMode"] = mode.lower() == "multi"

    authority = get_first(query, "authority") or get_first(query, "host")
    if authority:
        grpc_settings["authority"] = authority

    stream_settings["grpcSettings"] = grpc_settings


def apply_httpupgrade_settings(stream_settings: dict, query: dict) -> None:
    path = get_first(query, "path", "/") or "/"
    host = get_first(query, "host")
    upgrade_settings = {"path": path}
    if host:
        upgrade_settings["host"] = host
    stream_settings["httpupgradeSettings"] = upgrade_settings


def apply_http_settings(stream_settings: dict, query: dict) -> None:
    path = get_first(query, "path", "/") or "/"
    host_list = split_csv(get_first(query, "host"))
    stream_settings["httpSettings"] = {"path": path}
    if host_list:
        stream_settings["httpSettings"]["host"] = host_list


def apply_xhttp_settings(stream_settings: dict, query: dict) -> None:
    path = get_first(query, "path", "/") or "/"
    host = get_first(query, "host")
    mode = get_first(query, "mode")
    xhttp_settings = {"path": path}
    if host:
        xhttp_settings["host"] = host
    if mode:
        xhttp_settings["mode"] = mode
    stream_settings["xhttpSettings"] = xhttp_settings


def apply_quic_settings(stream_settings: dict, query: dict) -> None:
    quic_security = get_first(query, "quicSecurity") or get_first(query, "security")
    key = get_first(query, "key")
    header_type = get_first(query, "headerType", "none") or "none"
    stream_settings["quicSettings"] = {
        "security": quic_security or "none",
        "key": key,
        "header": {"type": header_type},
    }


def apply_stream_settings(stream_settings: dict, network: str, query: dict) -> None:
    normalized = network.lower().strip()
    alias_map = {
        "gun": "grpc",
        "raw": "tcp",
        "h2": "http",
        "http": "http",
        "httpupgrade": "httpupgrade",
        "http-upgrade": "httpupgrade",
        "splithttp": "xhttp",
    }
    normalized = alias_map.get(normalized, normalized or "tcp")
    stream_settings["network"] = normalized

    if normalized == "ws":
        apply_ws_settings(stream_settings, query)
    elif normalized == "grpc":
        apply_grpc_settings(stream_settings, query)
    elif normalized == "httpupgrade":
        apply_httpupgrade_settings(stream_settings, query)
    elif normalized == "http":
        apply_http_settings(stream_settings, query)
    elif normalized == "xhttp":
        apply_xhttp_settings(stream_settings, query)
    elif normalized == "quic":
        apply_quic_settings(stream_settings, query)
    elif normalized == "tcp":
        apply_tcp_settings(stream_settings, query)


def build_vmess_outbound(link: str) -> dict:
    raw = decode_b64_urlsafe(link[len("vmess://"):])
    vmess = json.loads(raw)

    host = str(vmess.get("add", "")).strip()
    if not host:
        fail("vmess link is missing host.")

    port = int(vmess.get("port", 443))
    user = {
        "id": str(vmess.get("id", "")).strip(),
        "alterId": int(vmess.get("aid", 0) or 0),
        "security": str(vmess.get("scy", "auto")).strip() or "auto",
    }

    outbound = {
        "protocol": "vmess",
        "settings": {
            "vnext": [
                {
                    "address": host,
                    "port": port,
                    "users": [user],
                }
            ]
        },
        "streamSettings": {},
    }

    network = str(vmess.get("net", "tcp")).strip() or "tcp"
    stream_settings = outbound["streamSettings"]
    stream_settings["network"] = "tcp"

    vmess_query = {
        "path": [str(vmess.get("path", "/") or "/")],
        "host": [str(vmess.get("host", "") or "")],
        "serviceName": [str(vmess.get("path", "") or "")],
        "mode": [str(vmess.get("mode", "") or "")],
        "type": [str(vmess.get("type", "") or "")],
        "headerType": [str(vmess.get("type", "") or "")],
        "sni": [str(vmess.get("sni", "") or "")],
        "serverName": [str(vmess.get("sni", "") or "")],
        "allowInsecure": [str(vmess.get("allowInsecure", "") or vmess.get("insecure", "") or "")],
        "alpn": [str(vmess.get("alpn", "") or "")],
        "fp": [str(vmess.get("fp", "") or vmess.get("fingerprint", "") or "")],
    }

    apply_stream_settings(stream_settings, network, vmess_query)

    tls_mode = str(vmess.get("tls", "none")).strip().lower()
    if tls_mode in {"tls", "xtls"}:
        vmess_query["security"] = ["tls"]
        add_tls_settings(stream_settings, host, vmess_query)

    return outbound


def build_vless_or_trojan_outbound(link: str) -> dict:
    parsed = urlsplit(link)
    proto = parsed.scheme.lower()
    query = parse_qs(parsed.query, keep_blank_values=True)

    host = parsed.hostname or ""
    if not host:
        fail(f"{proto} link is missing host.")

    port = parsed.port or 443
    credential = unquote(parsed.username or "")
    if not credential:
        fail(f"{proto} link is missing credential.")

    stream_settings = {}
    apply_stream_settings(stream_settings, get_first(query, "type", "tcp"), query)
    add_tls_settings(stream_settings, host, query)

    if proto == "vless":
        user = {
            "id": credential,
            "encryption": get_first(query, "encryption", "none") or "none",
        }
        flow = get_first(query, "flow")
        if flow:
            user["flow"] = flow
        settings = {
            "vnext": [
                {
                    "address": host,
                    "port": port,
                    "users": [user],
                }
            ]
        }
    else:
        settings = {
            "servers": [
                {
                    "address": host,
                    "port": port,
                    "password": credential,
                }
            ]
        }

    return {
        "protocol": proto,
        "settings": settings,
        "streamSettings": stream_settings,
    }


def build_socks_outbound(link: str) -> dict:
    parsed = urlsplit(link)
    host = parsed.hostname or ""
    if not host:
        fail("socks link is missing host.")

    server = {"address": host, "port": parsed.port or 1080}
    if parsed.username:
        server["users"] = [
            {
                "user": unquote(parsed.username),
                "pass": unquote(parsed.password or ""),
            }
        ]

    return {
        "protocol": "socks",
        "settings": {"servers": [server]},
    }


def build_http_outbound(link: str) -> dict:
    parsed = urlsplit(link)
    host = parsed.hostname or ""
    if not host:
        fail("http proxy link is missing host.")

    server = {"address": host, "port": parsed.port or 8080}
    if parsed.username:
        server["users"] = [
            {
                "user": unquote(parsed.username),
                "pass": unquote(parsed.password or ""),
            }
        ]

    return {
        "protocol": "http",
        "settings": {"servers": [server]},
    }


def build_outbound(link: str) -> dict:
    if link.startswith("vmess://"):
        return build_vmess_outbound(link)
    if link.startswith("vless://") or link.startswith("trojan://"):
        return build_vless_or_trojan_outbound(link)
    if link.startswith("socks5://") or link.startswith("socks://"):
        return build_socks_outbound(link)
    if link.startswith("http://") or link.startswith("https://"):
        return build_http_outbound(link)
    fail(f"unsupported proxy protocol: {link.split('://', 1)[0]}")


def main() -> None:
    link = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PROXY", "")).strip()
    if not link:
        fail("PROXY is empty.")

    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "port": 10808,
                "protocol": "socks",
                "settings": {"udp": True},
            }
        ],
        "outbounds": [build_outbound(link)],
    }

    with open("config.json", "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)

    protocol = config["outbounds"][0]["protocol"]
    network = config["outbounds"][0].get("streamSettings", {}).get("network", "direct")
    security = config["outbounds"][0].get("streamSettings", {}).get("security", "none")
    print(
        f"Built config.json for protocol={protocol}, network={network}, security={security}.",
        flush=True,
    )


if __name__ == "__main__":
    main()
