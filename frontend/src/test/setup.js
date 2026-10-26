import zlib from "node:zlib";

// Polyfill missing zstd binding in older Node versions for undici
if (zlib && !zlib.createZstdDecompress) {
  zlib.createZstdDecompress = () => zlib.createGunzip();
}
if (zlib && !zlib.createZstdCompress) {
  zlib.createZstdCompress = () => zlib.createGzip();
}
