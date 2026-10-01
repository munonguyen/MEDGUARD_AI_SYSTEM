import { existsSync, readFileSync, writeFileSync, chmodSync, mkdirSync } from 'node:fs';
import { brotliDecompressSync } from 'node:zlib';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import chromium from '@sparticuz/chromium';
export function runtime() {
  if (process.env.CHROME_PATH) return { executablePath: process.env.CHROME_PATH, args: ['--no-sandbox'] };
  const require = createRequire(import.meta.url);
  const bin = join(require.resolve('@sparticuz/chromium'), '../../bin');
  const executablePath = join(tmpdir(), 'medguard-chromium');
  if (!existsSync(executablePath)) {
    writeFileSync(executablePath, brotliDecompressSync(readFileSync(join(bin, 'chromium.br'))));
    chmodSync(executablePath, 0o755);
  }
  const fonts = join(tmpdir(), 'medguard-fonts');
  if (!existsSync(join(fonts, 'fonts.conf'))) {
    mkdirSync(fonts, { recursive: true });
    const archive = join(tmpdir(), 'medguard-fonts.tar');
    writeFileSync(archive, brotliDecompressSync(readFileSync(join(bin, 'fonts.tar.br'))));
    execFileSync('tar', ['--no-same-owner', '--no-same-permissions', '-xf', archive, '-C', fonts]);
  }
  writeFileSync(join(fonts, 'fonts.conf'), `<fontconfig><dir>${fonts}/fonts</dir><cachedir>${fonts}/cache</cachedir></fontconfig>`);
  return { executablePath, args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--use-gl=disabled'], env: { ...process.env, FONTCONFIG_PATH: fonts } };
}
