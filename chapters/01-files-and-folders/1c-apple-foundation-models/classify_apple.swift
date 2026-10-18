// Classify files with Apple's on-device model. No download, no server, no network.
//
//   swiftc -O classify_apple.swift -o classify_apple
//   ./classify_apple <folder> [output.json]
//
// Needs macOS 26+ on a Mac with Apple Intelligence turned on.
// Same idea as 1B: the model can only answer from two fixed lists. Here the
// guarantee comes from @Generable enums (guided generation) instead of a JSON
// schema. Output is the same classification.json that make_plan.py reads.

import Foundation
import FoundationModels

@Generable
enum Category: String, CaseIterable {
    case documents, images, spreadsheets, installers, archives, text, review

    var label: String { rawValue.prefix(1).uppercased() + rawValue.dropFirst() }
}

@Generable
enum Sensitivity: String {
    case none, personal, financial, health, credentials, government_id, legal
}

@Generable
struct Classification {
    @Guide(description: "What the file actually is, judged by content and name. Use review if unclear, empty or meaningless.")
    var category: Category

    @Guide(description: "Sensitive data kind: personal (resumes, contacts), financial (invoices, tax, budgets), health, credentials, government_id (SSN, W-2), legal (leases, contracts), or none. If unsure, choose a sensitive kind, not none.")
    var sensitivity: Sensitivity
}

// PDFs and images: ask the extract_text helper (PDF text layer, or on-device OCR for scans
// and screenshots). It sits next to this program. Without it they are judged by filename only.
let extractSuffixes: Set<String> = ["pdf", "png", "jpg", "jpeg", "heic", "tif", "tiff", "gif", "bmp", "webp"]
let helperURL = URL(fileURLWithPath: CommandLine.arguments[0])
    .deletingLastPathComponent().appendingPathComponent("extract_text")

func extractedText(from url: URL, limit: Int) -> String? {
    guard extractSuffixes.contains(url.pathExtension.lowercased()),
          FileManager.default.isExecutableFile(atPath: helperURL.path) else { return nil }
    let process = Process()
    let pipe = Pipe()
    process.executableURL = helperURL
    process.arguments = [url.path, String(limit)]
    process.standardOutput = pipe
    process.standardError = FileHandle.nullDevice
    guard (try? process.run()) != nil else { return nil }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    process.waitUntilExit()
    guard process.terminationStatus == 0 else { return nil }
    let text = String(decoding: data, as: UTF8.self)
    return text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : String(text.prefix(limit))
}

func head(of url: URL, limit: Int = 2000) -> String {
    if let text = extractedText(from: url, limit: limit) { return text }
    // Read only the start of the file, never the whole thing (it could be many GB).
    guard let handle = try? FileHandle(forReadingFrom: url),
          let slice = try? handle.read(upToCount: limit) else { return "[unreadable]" }
    try? handle.close()
    if slice.contains(0) {
        let size = (try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0
        return "[binary file, \(size) bytes]"
    }
    return String(decoding: slice, as: UTF8.self)
}

let topLevel = CommandLine.arguments.contains("--top-level")  // direct files only; subfolders never opened
let args = CommandLine.arguments.filter { $0 != "--top-level" }
guard args.count >= 2 else {
    print("usage: classify_apple <folder> [output.json] [--top-level]")
    exit(2)
}
let folder = URL(fileURLWithPath: args[1])
var isFolder: ObjCBool = false
guard FileManager.default.fileExists(atPath: folder.path, isDirectory: &isFolder), isFolder.boolValue else {
    print("Not a folder: \(folder.path)")
    exit(2)
}
let outURL = args.count > 2
    ? URL(fileURLWithPath: args[2])
    : folder.deletingLastPathComponent().appendingPathComponent("classification.json")

guard case .available = SystemLanguageModel.default.availability else {
    print("Apple's on-device model is not available (needs macOS 26+, Apple Intelligence on).")
    exit(1)
}

let instructions = """
You classify one file at a time for a file-tidying tool. You get the file name \
and the first part of its content. Judge by what the file is, not only its extension.
"""

func listFiles(in folder: URL, topLevelOnly: Bool) -> [URL] {
    var found: [URL] = []
    let options: FileManager.DirectoryEnumerationOptions = topLevelOnly ? [.skipsSubdirectoryDescendants] : []
    if let walker = FileManager.default.enumerator(at: folder, includingPropertiesForKeys: [.isRegularFileKey], options: options) {
        for case let url as URL in walker
        where (try? url.resourceValues(forKeys: [.isRegularFileKey]))?.isRegularFile == true
            && url.lastPathComponent != ".DS_Store" {
            found.append(url)
        }
    }
    return found.sorted { $0.path < $1.path }
}
let files = listFiles(in: folder, topLevelOnly: topLevel)

// The enumerator hands back resolved paths (/private/tmp/...) even when the folder was given through a
// link (/tmp/...), so cutting the folder path's length off each one would give broken keys. Resolve both
// and compare whole path components instead.
let rootParts = folder.resolvingSymlinksInPath().standardizedFileURL.pathComponents
func relativePath(of url: URL) -> String? {
    let parts = url.resolvingSymlinksInPath().standardizedFileURL.pathComponents
    guard parts.count > rootParts.count, Array(parts.prefix(rootParts.count)) == rootParts else { return nil }
    return parts.dropFirst(rootParts.count).joined(separator: "/")
}

var results: [String: [String: String]] = [:]
for (i, url) in files.enumerated() {
    guard let rel = relativePath(of: url) else {
        print("Cannot place \(url.path) inside \(folder.path). Nothing was written.")
        exit(1)
    }
    // A fresh session per file: the context window is small, and files must not influence each other.
    let prompt = "File name: \(url.lastPathComponent)\n\nContent start:\n\(head(of: url))"
    var lastError: Error?
    for attempt in 1...2 {  // the on-device service can fail transiently when the Mac is busy
        do {
            let session = LanguageModelSession(instructions: instructions)
            let reply = try await session.respond(to: prompt, generating: Classification.self)
            results[rel] = ["category": reply.content.category.label,
                            "sensitivity": reply.content.sensitivity.rawValue]
            print("[\(i + 1)/\(files.count)] \(rel): \(reply.content.category.label) / \(reply.content.sensitivity.rawValue)")
            lastError = nil
            break
        } catch {
            lastError = error
            if attempt == 1 { try? await Task.sleep(nanoseconds: 1_000_000_000) }
        }
    }
    if let error = lastError {
        // Includes the model's own safety guardrails. Fail closed: no label means Review + sensitive.
        print("  ! \(rel): \(error)")
    }
}

let json = try JSONSerialization.data(withJSONObject: results, options: [.prettyPrinted, .sortedKeys])
try json.write(to: outURL)
print("Wrote \(outURL.path) (\(results.count) of \(files.count) files labeled)")
