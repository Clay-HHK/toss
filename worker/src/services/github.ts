/**
 * GitHub API service for identity verification.
 */

const GITHUB_API = "https://api.github.com";
const GITHUB_DEVICE_URL = "https://github.com/login/device/code";
const GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token";

export interface GitHubUser {
  id: number;
  login: string;
  name: string | null;
  avatar_url: string;
}

export interface DeviceCodeResponse {
  device_code: string;
  user_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
}

export interface TokenResponse {
  access_token?: string;
  error?: string;
}

export async function getGitHubUserByPAT(pat: string): Promise<GitHubUser> {
  const resp = await fetch(`${GITHUB_API}/user`, {
    headers: {
      Authorization: `Bearer ${pat}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "toss-worker",
    },
  });

  if (!resp.ok) {
    throw new Error(`GitHub API error: ${resp.status}`);
  }

  return resp.json() as Promise<GitHubUser>;
}

export async function startDeviceFlow(clientId: string): Promise<DeviceCodeResponse> {
  const resp = await fetch(GITHUB_DEVICE_URL, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      client_id: clientId,
      scope: "read:user",
    }),
  });

  if (!resp.ok) {
    throw new Error(`GitHub device flow error: ${resp.status}`);
  }

  return resp.json() as Promise<DeviceCodeResponse>;
}

export async function exchangeDeviceCode(
  clientId: string,
  deviceCode: string,
): Promise<TokenResponse> {
  const resp = await fetch(GITHUB_TOKEN_URL, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      client_id: clientId,
      device_code: deviceCode,
      grant_type: "urn:ietf:params:oauth:grant-type:device_code",
    }),
  });

  if (!resp.ok) {
    throw new Error(`GitHub token exchange error: ${resp.status}`);
  }

  return resp.json() as Promise<TokenResponse>;
}
