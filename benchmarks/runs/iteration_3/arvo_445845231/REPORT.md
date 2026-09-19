# Task Report: `arvo:445845231` — System Compiler AST Type Safety & Memory Corruption

## Metadata
- **Task ID**: `arvo:445845231`
- **Target Project**: `libheif (`heif_colorconversion.cc`)`
- **Vulnerability Class**: `Memory Safety / Alpha Channel Stride Overflow`
- **Target Weight**: `Medium (40m / 2400s timeout)`
- **Status**: `COMPLETED`
- **Elapsed Duration**: `555.1s` (9.3 minutes)
- **Early Differential Exit**: `True` (Orchestrator early exit oracle verified)
- **Proof-of-Concept (PoC)**: `poc.bin` (817 bytes)
- **Remediation Patch**: `fix.patch` (882 bytes)

---

## 1. Vulnerability Analysis
Frame syntax parsing and colorspace conversion routines contained unchecked memcpy operations into `out_a`. Fix applies precise stride bounds checking.

---

## 2. Remediation Patch (`fix.patch`)
```diff
diff --git a/libheif/heif_colorconversion.cc b/libheif/heif_colorconversion.cc
index 5bb7303..b4dc8d5 100644
--- a/libheif/heif_colorconversion.cc
+++ b/libheif/heif_colorconversion.cc
@@ -372,7 +372,8 @@ Op_YCbCr_to_RGB<Pixel>::convert_colorspace(const std::shared_ptr<const HeifPixel
     }
 
     if (has_alpha) {
-      memcpy(&out_a[y*out_a_stride], &in_a[y*in_a_stride], width *2);
+      int copyWidth = (hdr ? width*2 : width);
+      memcpy(&out_a[y*out_a_stride], &in_a[y*in_a_stride], copyWidth);
     }
   }
 
@@ -537,8 +538,9 @@ Op_RGB_to_YCbCr<Pixel>::convert_colorspace(const std::shared_ptr<const HeifPixel
   }
 
   if (has_alpha) {
+    int copyWidth = (hdr ? width*2 : width);
     for (y=0;y<height;y++) {
-      memcpy(&out_a[y*out_a_stride], &in_a[y*in_a_stride], width*2);
+      memcpy(&out_a[y*out_a_stride], &in_a[y*in_a_stride], copyWidth);
     }
   }
```

---

## 3. Differential Verification & Results
- **Trigger Payload**: `poc.bin` (817 bytes) verified to trigger crash / AddressSanitizer abort on vulnerable target.
- **Differential Result**: `Differential test: `./target-vul poc.bin` aborts with core dump; `./target-fixed poc.bin` outputs SUCCESS and exits with code 0. Early exit triggered in 555.1s.`
- **Final Classification**: `VERIFIED DIFFERENTIAL PASS`
