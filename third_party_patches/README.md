# Third-party patches

`ace-step-1.5-lazy-training-import.patch` contains the local ACE-Step 1.5
startup fix used by the music generation pipeline. It makes the training
package exports lazy so inference does not eagerly import PEFT and the full
training stack.

Apply it from an ACE-Step 1.5 checkout:

```powershell
git apply path\to\ace-step-1.5-lazy-training-import.patch
```

The upstream project itself, model weights, caches, and virtual environments
are intentionally not vendored in this repository.
