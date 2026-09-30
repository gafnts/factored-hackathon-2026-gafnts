export interface Config {
  region: string;
  user_pool_id: string;
  customer_client_id: string;
  staff_client_id: string;
  runtime_url: string;
}

const KEYS = [
  "region",
  "user_pool_id",
  "customer_client_id",
  "staff_client_id",
  "runtime_url",
] as const;

export class ConfigError extends Error {
  override name = "ConfigError";
}

function isConfig(value: unknown): value is Config {
  if (typeof value !== "object" || value === null) return false;
  const fields = value as Record<string, unknown>;
  return (
    KEYS.every(
      (key) => typeof fields[key] === "string" && fields[key] !== "",
    ) && String(fields.runtime_url).startsWith("https://")
  );
}

// Written by Terraform at every apply (infra/modules/site), so the same build runs in any environment.
export async function loadConfig(): Promise<Config> {
  const response = await fetch("/config.json", { cache: "no-cache" });
  if (!response.ok)
    throw new ConfigError(`config.json: HTTP ${String(response.status)}`);
  const value: unknown = await response.json();
  if (!isConfig(value)) throw new ConfigError("config.json lacks a field");
  return value;
}
