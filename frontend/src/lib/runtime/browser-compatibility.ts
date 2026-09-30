// Safari 15.3.1 baseline. Load once, before client routes and their dependencies.
import "core-js/actual/array/at"; // modal focus, editor and bundled dependencies
import "core-js/actual/array/find-last"; // Tiptap/ProseMirror editing
import "core-js/actual/object/has-own"; // SvelteKit client runtime
import "core-js/actual/structured-clone"; // XYFlow node/connection snapshots
import "core-js/actual/promise/with-resolvers"; // XYFlow fitView camera actions
import { installFormCompatibility } from "./form-compatibility";

installFormCompatibility(); // SvelteKit needs button submitters and FormData(form, submitter).
