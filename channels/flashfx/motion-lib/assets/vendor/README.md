# Vendored browser libraries

Copied from node_modules by `bash pipeline/bin/setup-node` (the versions are pinned in package.json):

- gsap.min.js: GSAP 3.15.0, GreenSock standard "no charge" license (https://gsap.com/standard-license), free for every use since 3.13.
- three.min.js: Three.js r159 (three@0.159.0), MIT, see three-LICENSE.txt.

The compositions load them with relative paths so a render needs no network.
