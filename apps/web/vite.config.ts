import http from "node:http";
import os from "node:os";
import { defineConfig } from "vite";

// Linux 上 inotify 上限较低时（ENOSPC），用轮询代替原生 watch
const usePolling = process.env.VITE_USE_POLLING === "1";

function proxyBase(host: string, port: string): string {
  const h = host.includes(":") ? `[${host}]` : host;
  return `http://${h}:${port}`;
}

function healthOk(host: string, port: string): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(
      { host, port: Number(port), path: "/health", timeout: 2000 },
      (res) => {
        let body = "";
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          resolve(
            res.statusCode === 200 &&
              body.includes("bonemet-workstation"),
          );
        });
      },
    );
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

/** 127.0.0.1:port 在 Windows 上常被 IDE 占用；回退到本机网卡 IP 以命中 0.0.0.0 上的 uvicorn */
async function resolveApiProxyHost(): Promise<string> {
  if (process.env.VITE_API_HOST) return process.env.VITE_API_HOST;
  const port = process.env.VITE_API_PORT || "10120";
  const candidates = ["127.0.0.1", "::1"];
  if (process.platform === "win32") {
    for (const ifaces of Object.values(os.networkInterfaces())) {
      for (const iface of ifaces ?? []) {
        const v4 =
          iface.family === "IPv4" || (iface.family as unknown) === 4;
        if (v4 && !iface.internal) candidates.push(iface.address);
      }
    }
  }
  for (const host of candidates) {
    if (await healthOk(host, port)) {
      if (host !== "127.0.0.1") {
        console.warn(
          `[vite] API 代理 → ${proxyBase(host, port)}（127.0.0.1:${port} 被其它程序占用，已自动改用本机 IP）`,
        );
      }
      return host;
    }
  }
  return "127.0.0.1";
}

export default defineConfig(async () => {
  const apiPort = process.env.VITE_API_PORT || "10120";
  const apiHost = await resolveApiProxyHost();
  const apiTarget = proxyBase(apiHost, apiPort);

  return {
    server: {
      port: Number(process.env.VITE_DEV_PORT || 10123),
      strictPort: true,
      host: process.env.VITE_HOST || "0.0.0.0",
      proxy: {
        "/api": apiTarget,
        "/health": apiTarget,
      },
      watch: usePolling
        ? { usePolling: true, interval: 1000 }
        : undefined,
    },
  };
});
