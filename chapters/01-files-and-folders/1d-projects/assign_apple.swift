// A bridge to Apple's on-device model for assign_projects.py. No download, no server, no network.
//
//   swiftc -O assign_apple.swift -o assign_apple
//
// Needs macOS 26+ on a Mac with Apple Intelligence turned on. You do not run this yourself.
// `assign_projects.py --apple ./assign_apple` starts it and talks to it over standard input and output.
//
// Each line on stdin is one JSON request: {"system": ..., "user": ..., "projects": [...], "sensitivities": [...]}.
// Each line on stdout is the answer: {"primary": ..., "also": [...], "sensitivity": ...}, or {"error": ...}.
// The answer can only hold the names it was given. The schema is built at run time from your project
// list, the same job the JSON schema does for LM Studio and Ollama.

import Foundation
import FoundationModels

guard case .available = SystemLanguageModel.default.availability else {
    print(#"{"error": "Apple's on-device model is not available (needs macOS 26+, Apple Intelligence on)."}"#)
    exit(1)
}

func reply(_ object: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: object), let line = String(data: data, encoding: .utf8) {
        print(line)
        fflush(stdout)
    }
}

while let line = readLine() {
    guard let data = line.data(using: .utf8),
          let request = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let system = request["system"] as? String, let user = request["user"] as? String,
          let projects = request["projects"] as? [String],
          let sensitivities = request["sensitivities"] as? [String] else {
        reply(["error": "bad request"])
        continue
    }
    do {
        let primary = DynamicGenerationSchema(name: "Primary", anyOf: projects + ["Unsorted"])
        let alsoItem = DynamicGenerationSchema(name: "AlsoItem", anyOf: projects)
        let also = DynamicGenerationSchema(arrayOf: alsoItem, minimumElements: 0, maximumElements: 2)
        let sensitivity = DynamicGenerationSchema(name: "Sensitivity", anyOf: sensitivities)
        let root = DynamicGenerationSchema(name: "Assignment", properties: [
            .init(name: "primary", schema: primary),
            .init(name: "also", schema: also),
            .init(name: "sensitivity", schema: sensitivity),
        ])
        let schema = try GenerationSchema(root: root, dependencies: [])
        // A fresh session per file: the context window is small, and files must not influence each other.
        let session = LanguageModelSession(instructions: system)
        let result = try await session.respond(to: user, schema: schema)
        reply(["primary": try result.content.value(String.self, forProperty: "primary"),
               "also": try result.content.value([String].self, forProperty: "also"),
               "sensitivity": try result.content.value(String.self, forProperty: "sensitivity")])
    } catch {
        reply(["error": "\(error)"])  // includes the model's own safety guardrails; the caller fails closed
    }
}
