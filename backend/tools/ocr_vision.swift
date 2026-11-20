// OCR hors ligne avec le framework Vision de macOS (aucun service externe).
// Compilation : swiftc -O tools/ocr_vision.swift -o bin/ocr-vision
// Usage : bin/ocr-vision image.png   → texte reconnu sur la sortie standard (UTF-8)
import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count == 2 else {
    FileHandle.standardError.write("usage: ocr-vision <image>\n".data(using: .utf8)!)
    exit(2)
}

let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let image = NSImage(contentsOf: url),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("image illisible\n".data(using: .utf8)!)
    exit(3)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["fr-FR", "en-US"]

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
} catch {
    FileHandle.standardError.write("échec OCR : \(error)\n".data(using: .utf8)!)
    exit(4)
}

// Ordre de lecture : les pages en deux colonnes sont lues colonne gauche puis colonne droite.
// Un bloc qui chevauche le milieu de la page (titre, consigne pleine largeur) sert de séparateur.
struct Line { let text: String; let box: CGRect }
let all = (request.results ?? []).compactMap { obs -> Line? in
    guard let text = obs.topCandidates(1).first?.string else { return nil }
    return Line(text: text, box: obs.boundingBox)
}
func topDown(_ items: [Line]) -> [Line] {
    items.sorted { a, b in
        let dy = a.box.midY - b.box.midY
        if abs(dy) > 0.01 { return dy > 0 }
        return a.box.minX < b.box.minX
    }
}
let left = all.filter { $0.box.maxX <= 0.52 }
let right = all.filter { $0.box.minX >= 0.48 }
let twoColumns = left.count >= 6 && right.count >= 6
    && Double(left.count + right.count) >= 0.6 * Double(all.count)
var ordered: [Line] = []
if !twoColumns {
    ordered = topDown(all)
} else {
    // Bandes verticales délimitées par les blocs pleine largeur.
    let full = topDown(all.filter { $0.box.maxX > 0.52 && $0.box.minX < 0.48 })
    var upper: CGFloat = 1.01
    func band(_ low: CGFloat, _ high: CGFloat) -> [Line] {
        let inBand = { (l: Line) in l.box.midY < high && l.box.midY >= low }
        return topDown(left.filter(inBand)) + topDown(right.filter(inBand))
    }
    for separator in full {
        ordered += band(separator.box.midY, upper)
        ordered.append(separator)
        upper = separator.box.midY
    }
    ordered += band(-0.01, upper)
}
print(ordered.map { $0.text }.joined(separator: "\n"))
