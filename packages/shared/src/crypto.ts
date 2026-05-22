import crypto from "crypto";

const ALGORITHM = "aes-256-cbc";
const SECRET = process.env["JWT_SECRET"] || "default-dev-secret-key-32-chars-long";
const KEY = crypto.createHash("sha256").update(SECRET).digest();
const IV_LENGTH = 16;

/** Encrypt a string using AES-256-CBC */
export function encrypt(text: string): string {
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, KEY, iv);
  let encrypted = cipher.update(text, "utf8", "hex");
  encrypted += cipher.final("hex");
  return iv.toString("hex") + ":" + encrypted;
}

/** Decrypt a string using AES-256-CBC */
export function decrypt(text: string): string {
  const parts = text.split(":");
  if (parts.length !== 2) {
    throw new Error("Invalid encrypted text format");
  }
  const iv = Buffer.from(parts[0]!, "hex");
  const encryptedText = Buffer.from(parts[1]!, "hex");
  const decipher = crypto.createDecipheriv(ALGORITHM, KEY, iv);
  let decrypted = decipher.update(encryptedText);
  decrypted = Buffer.concat([decrypted, decipher.final()]);
  return decrypted.toString("utf8");
}
