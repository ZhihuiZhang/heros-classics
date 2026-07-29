#!/usr/bin/env node

import { readFile, readdir, stat } from "node:fs/promises";
import { dirname, extname, join, relative, resolve, sep } from "node:path";

const options = Object.fromEntries(
  process.argv.slice(2).reduce((items, value, index, args) => {
    if (value.startsWith("--")) items.push([value.slice(2), args[index + 1]?.startsWith("--") ? true : args[index + 1] ?? true]);
    return items;
  }, []),
);
const root = resolve(String(options.root ?? "."));
const domain = String(options.domain ?? "").replace(/^https?:\/\//, "").replace(/\/$/, "");
const details = options.details === true;
const strict = options.strict === true;

async function walk(directory) {
  const result = [];
  const pending = [directory];
  while (pending.length) {
    const current = pending.pop();
    for (const entry of await readdir(current, { withFileTypes: true })) {
      if ([".git", "node_modules", ".venv"].includes(entry.name)) continue;
      const path = join(current, entry.name);
      if (entry.isDirectory()) pending.push(path);
      else if (entry.isFile()) result.push(path);
    }
  }
  return result;
}

function imageType(buffer) {
  if (buffer.length >= 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) return "jpeg";
  if (buffer.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) return "png";
  if (["GIF87a", "GIF89a"].includes(buffer.subarray(0, 6).toString("ascii"))) return "gif";
  if (buffer.subarray(0, 4).toString("ascii") === "RIFF" && buffer.subarray(8, 12).toString("ascii") === "WEBP") return "webp";
  const start = buffer.subarray(0, 1024).toString("utf8").trimStart();
  if (/^<svg[\s>]/i.test(start) || /^<\?xml[\s\S]*?<svg[\s>]/i.test(start)) return "svg";
  return null;
}

async function existsAsTarget(path) {
  try {
    const metadata = await stat(path);
    if (metadata.isFile()) return true;
    if (metadata.isDirectory()) return (await stat(join(path, "index.html"))).isFile();
  } catch {}
  if (!extname(path)) {
    try {
      return (await stat(`${path}.html`)).isFile();
    } catch {}
  }
  return false;
}

function localTarget(source, raw) {
  let value = raw.trim().replaceAll("&amp;", "&");
  if (!value || /^(?:#|data:|mailto:|tel:|javascript:|blob:)/i.test(value) || /^\/\//.test(value)) return null;
  if (/^https?:\/\//i.test(value)) {
    try {
      const url = new URL(value);
      if (!domain || url.hostname !== domain) return null;
      value = url.pathname;
    } catch {
      return { path: null, reason: "malformed-url" };
    }
  }
  value = value.split(/[?#]/, 1)[0];
  try {
    value = decodeURIComponent(value);
  } catch {
    return { path: null, reason: "malformed-encoding" };
  }
  if (!value) return null;
  const path = value.startsWith("/") ? resolve(root, `.${value}`) : resolve(dirname(source), value);
  if (path !== root && !path.startsWith(`${root}${sep}`)) return { path, reason: "outside-root" };
  return { path, reason: null };
}

const files = await walk(root);
const htmlFiles = files.filter((file) => /\.html?$/i.test(file));
const imageFiles = files.filter((file) => /\.(?:jpe?g|png|gif|webp|svg)$/i.test(file));
const invalidImages = [];
for (const file of imageFiles) {
  if (!imageType(await readFile(file))) invalidImages.push(relative(root, file));
}

const brokenImages = [];
const brokenLinks = [];
const brokenResources = [];
const duplicateIds = [];
const missingH1 = [];
const missingAlt = [];
const malformedDocuments = [];
const canonicalUrls = [];
const noindexUrls = [];

async function checkReference(collection, file, reference, kind) {
  const target = localTarget(file, reference);
  if (!target) return;
  if (!target.path || !(await existsAsTarget(target.path))) {
    collection.push({ file: relative(root, file), reference, reason: target.reason ?? "missing-file" });
    return;
  }
  if (kind === "image" && /\.(?:jpe?g|png|gif|webp|svg)$/i.test(target.path)) {
    try {
      if (!imageType(await readFile(target.path))) {
        collection.push({ file: relative(root, file), reference, reason: "invalid-image" });
      }
    } catch {}
  }
}

for (const file of htmlFiles) {
  const source = await readFile(file, "utf8");
  const repoPath = relative(root, file);
  if (!/<h1\b/i.test(source)) missingH1.push(repoPath);
  if ((source.match(/<!doctype\s+html/gi) ?? []).length !== 1 || (source.match(/<html\b/gi) ?? []).length !== 1) {
    malformedDocuments.push(repoPath);
  }
  const ids = [...source.matchAll(/\bid\s*=\s*(["'])(.*?)\1/gi)].map((match) => match[2]);
  const repeated = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
  if (repeated.length) duplicateIds.push({ file: repoPath, ids: repeated });
  const canonical = source.match(/<link\b[^>]*rel\s*=\s*(["'])canonical\1[^>]*href\s*=\s*(["'])(.*?)\2/i)?.[3]
    ?? source.match(/<link\b[^>]*href\s*=\s*(["'])(.*?)\1[^>]*rel\s*=\s*(["'])canonical\3/i)?.[2];
  if (canonical) {
    canonicalUrls.push(canonical);
    if (/<meta\b[^>]*name\s*=\s*(["'])robots\1[^>]*content\s*=\s*(["'])[^"']*noindex/i.test(source)) {
      noindexUrls.push(canonical);
    }
  }
  for (const match of source.matchAll(/<img\b([^>]*)>/gi)) {
    const attrs = match[1];
    const src = attrs.match(/\bsrc\s*=\s*(["'])(.*?)\1/i)?.[2];
    if (!/\balt\s*=/i.test(attrs)) missingAlt.push({ file: repoPath, reference: src ?? "" });
    if (!src) brokenImages.push({ file: repoPath, reference: "", reason: "missing-src" });
    else await checkReference(brokenImages, file, src, "image");
  }
  for (const match of source.matchAll(/<a\b[^>]*href\s*=\s*(["'])(.*?)\1/gi)) {
    await checkReference(brokenLinks, file, match[2], "link");
  }
  for (const match of source.matchAll(/<(?:script|source|embed)\b[^>]*src\s*=\s*(["'])(.*?)\1/gi)) {
    await checkReference(brokenResources, file, match[2], "resource");
  }
  for (const match of source.matchAll(/<link\b[^>]*href\s*=\s*(["'])(.*?)\1/gi)) {
    await checkReference(brokenResources, file, match[2], "resource");
  }
}

for (const file of files.filter((item) => /\.css$/i.test(item))) {
  const source = await readFile(file, "utf8");
  for (const match of source.matchAll(/url\(\s*(["']?)(.*?)\1\s*\)/gi)) {
    await checkReference(brokenResources, file, match[2], "resource");
  }
}

let sitemapUrls = [];
try {
  const sitemap = await readFile(join(root, "sitemap.xml"), "utf8");
  sitemapUrls = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1].replaceAll("&amp;", "&"));
} catch {}
const sitemapSet = new Set(sitemapUrls);
const duplicateSitemapUrls = [...new Set(sitemapUrls.filter((url, index) => sitemapUrls.indexOf(url) !== index))];
const noindexPagesInSitemap = noindexUrls.filter((url) => sitemapSet.has(url));
const indexablePagesMissingFromSitemap = canonicalUrls.filter((url) => !noindexUrls.includes(url) && !sitemapSet.has(url));

const findings = {
  invalidImages,
  brokenImages,
  brokenLinks,
  brokenResources,
  duplicateIds,
  missingH1,
  missingAlt,
  malformedDocuments,
  duplicateSitemapUrls,
  noindexPagesInSitemap,
  indexablePagesMissingFromSitemap,
};
const summary = {
  files: files.length,
  htmlFiles: htmlFiles.length,
  imageFiles: imageFiles.length,
  ...Object.fromEntries(Object.entries(findings).map(([key, value]) => [key, value.length])),
};
console.log(JSON.stringify(details ? { summary, findings } : { summary }, null, 2));
if (strict && Object.entries(summary).some(([key, value]) =>
  !["files", "htmlFiles", "imageFiles"].includes(key) && value > 0
)) {
  process.exitCode = 1;
}
