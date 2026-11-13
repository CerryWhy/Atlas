// Copia il decoder Draco di three in public/, così non dipendiamo da un CDN esterno.
import { cpSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const src = fileURLToPath(new URL("../node_modules/three/examples/jsm/libs/draco/gltf/", import.meta.url));
const dst = fileURLToPath(new URL("../public/draco/", import.meta.url));
mkdirSync(dst, { recursive: true });
cpSync(src, dst, { recursive: true });
