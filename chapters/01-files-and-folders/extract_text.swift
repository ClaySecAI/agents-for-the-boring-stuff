// Pull a short text excerpt out of a PDF or image, entirely on this Mac.
//
//   swiftc -O extract_text.swift -o extract_text
//   ./extract_text <file> [max_chars]        (default 2000)
//
// PDF    -> its text layer (PDFKit). If the PDF is a scan with no text, the first
//           page is rendered and read with on-device OCR (Vision).
// Image  -> on-device OCR text, plus the top few scene labels ("document", "dog"...).
// Other  -> prints nothing and exits 3, so the caller falls back to its own reader.
//
// Both classifiers (1B and 1C) call this, so a PDF or screenshot is judged by what
// it says, not just by its filename. Nothing leaves the machine and no model is
// downloaded: PDFKit and Vision ship with macOS.

import AppKit
import Foundation
import ImageIO
import PDFKit
import Vision

let imageExtensions: Set<String> = ["png", "jpg", "jpeg", "heic", "tif", "tiff", "gif", "bmp", "webp"]
let maxBytes = 300 * 1024 * 1024  // do not even try on huge files

func recognizeText(in image: CGImage) -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    try? VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    return (request.results ?? [])
        .compactMap { $0.topCandidates(1).first?.string }
        .joined(separator: "\n")
}

func sceneLabels(of image: CGImage) -> [String] {
    let request = VNClassifyImageRequest()
    try? VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    return (request.results ?? [])
        .filter { $0.confidence > 0.3 }
        .sorted { $0.confidence > $1.confidence }
        .prefix(3)
        .map { $0.identifier.replacingOccurrences(of: "_", with: " ") }
}

// Transparent PNGs (many screenshots and exports) otherwise read as black-on-black.
func flattenedOnWhite(_ image: CGImage) -> CGImage {
    let rect = CGRect(x: 0, y: 0, width: image.width, height: image.height)
    guard let context = CGContext(
        data: nil, width: image.width, height: image.height, bitsPerComponent: 8, bytesPerRow: 0,
        space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)
    else { return image }
    context.setFillColor(CGColor(gray: 1, alpha: 1))
    context.fill(rect)
    context.draw(image, in: rect)
    return context.makeImage() ?? image
}

func loadImage(_ url: URL) -> CGImage? {
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { return nil }
    return flattenedOnWhite(image)
}

func renderFirstPage(of document: PDFDocument) -> CGImage? {
    guard let page = document.page(at: 0) else { return nil }
    let box = page.bounds(for: .mediaBox)
    guard box.width > 0, box.height > 0 else { return nil }
    let scale = 1600 / max(box.width, box.height)
    let size = CGSize(width: box.width * scale, height: box.height * scale)
    var rect = CGRect(origin: .zero, size: size)
    return page.thumbnail(of: size, for: .mediaBox).cgImage(forProposedRect: &rect, context: nil, hints: nil)
}

func excerpt(of url: URL, limit: Int) -> String? {
    let ext = url.pathExtension.lowercased()
    if ext == "pdf" {
        guard let document = PDFDocument(url: url) else { return nil }
        var text = ""
        for index in 0..<min(document.pageCount, 5) where text.count < limit {
            text += (document.page(at: index)?.string ?? "") + "\n"
        }
        if text.trimmingCharacters(in: .whitespacesAndNewlines).count >= 20 { return text }
        guard let page = renderFirstPage(of: document) else { return nil }
        return "(scanned PDF, text read by OCR)\n" + recognizeText(in: page)
    }
    if imageExtensions.contains(ext) {
        guard let image = loadImage(url) else { return nil }
        let labels = sceneLabels(of: image)
        let text = recognizeText(in: image)
        return "(image) scene: \(labels.isEmpty ? "unknown" : labels.joined(separator: ", "))\ntext in image:\n\(text)"
    }
    return nil
}

let args = CommandLine.arguments
guard args.count >= 2 else {
    FileHandle.standardError.write(Data("usage: extract_text <file> [max_chars]\n".utf8))
    exit(2)
}
let url = URL(fileURLWithPath: args[1])
let limit = args.count > 2 ? (Int(args[2]) ?? 2000) : 2000
let size = (try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0
guard size <= maxBytes, let text = excerpt(of: url, limit: limit) else { exit(3) }
print(String(text.prefix(limit)))
