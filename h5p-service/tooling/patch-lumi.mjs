/** Adapt the pinned Lumi image upload to image-size 2's bounded async file API. */
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const target = fileURLToPath(new URL('../node_modules/@lumieducation/h5p-server/build/src/H5PEditor.js', import.meta.url));
const originalHash = 'e350d632670d9d71ffd6320a1e8b36aeb266d5db10f4a17ac9bee71b4f0c343c';
const before = 'imageDimensions = (0, image_size_1.default)(file.data?.length > 0 ? file.data : file.tempFilePath);';
const after = 'imageDimensions = file.data?.length > 0 ? (0, image_size_1.default)(file.data) : await require("image-size/fromFile").imageSizeFromFile(file.tempFilePath);';
let source = readFileSync(target, 'utf8');
// Idempotence is limited to the exact transformation, not a marker in arbitrary code.
const unpatched = source.replace(after, before);
if (createHash('sha256').update(unpatched).digest('hex') !== originalHash) {
  throw new Error('Unreviewed Lumi H5PEditor source; review the image-size compatibility patch');
}
source = unpatched.replace(before, after);
writeFileSync(target, source);
