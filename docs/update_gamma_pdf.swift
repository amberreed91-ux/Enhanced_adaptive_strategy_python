import Foundation
import PDFKit
import CoreGraphics

let inputPath = "/Users/amberreed/Downloads/Chimera-Beginner-Walkthrough-Playbook.pdf"
let outputPath = "/Users/amberreed/Enhanced_adaptive_strategy_python/docs/Chimera-Beginner-Walkthrough-Playbook.updated.pdf"

guard let srcDoc = PDFDocument(url: URL(fileURLWithPath: inputPath)), srcDoc.pageCount > 0 else {
    fputs("Failed to open source PDF\n", stderr)
    exit(1)
}

let outDoc = PDFDocument()

func addCover(from templatePage: PDFPage, to doc: PDFDocument) {
    guard let cover = templatePage.copy() as? PDFPage else { return }
    let b = cover.bounds(for: .mediaBox)

    // Full-page dark background.
    let bg = PDFAnnotation(bounds: b, forType: .square, withProperties: nil)
    bg.color = .clear
    bg.interiorColor = NSColor(calibratedRed: 0.03, green: 0.09, blue: 0.20, alpha: 1.0)
    bg.border = PDFBorder()
    bg.border?.lineWidth = 0
    cover.addAnnotation(bg)

    func text(_ str: String, x: CGFloat, y: CGFloat, size: CGFloat, rgb: (CGFloat, CGFloat, CGFloat), bold: Bool = false) {
        let rect = CGRect(x: x, y: y, width: b.width * 0.85, height: 90)
        let ann = PDFAnnotation(bounds: rect, forType: .freeText, withProperties: nil)
        ann.font = bold ? .boldSystemFont(ofSize: size) : .systemFont(ofSize: size)
        ann.fontColor = NSColor(calibratedRed: rgb.0, green: rgb.1, blue: rgb.2, alpha: 1.0)
        ann.color = .clear
        ann.contents = str
        ann.alignment = .left
        cover.addAnnotation(ann)
    }

    text("CHIMERA EXECUTION PLAYBOOK", x: b.width * 0.10, y: b.height * 0.70, size: 22, rgb: (0.98, 0.78, 0.27), bold: true)
    text("Chimera APP for Dummies", x: b.width * 0.10, y: b.height * 0.60, size: 52, rgb: (1.0, 1.0, 1.0), bold: true)
    text("by Amber Reed", x: b.width * 0.10, y: b.height * 0.52, size: 30, rgb: (0.90, 0.93, 0.98), bold: false)

    doc.insert(cover, at: 0)
}

if let first = srcDoc.page(at: 0) {
    addCover(from: first, to: outDoc)
}

for i in 0..<srcDoc.pageCount {
    guard let pageCopy = srcDoc.page(at: i)?.copy() as? PDFPage else { continue }
    let b = pageCopy.bounds(for: .mediaBox)

    // Hide Gamma watermark area in top-right corner.
    let maskW = min(CGFloat(170), b.width * 0.22)
    let maskH = min(CGFloat(44), b.height * 0.07)
    let maskRect = CGRect(x: b.width - maskW - 6, y: b.height - maskH - 6, width: maskW, height: maskH)
    let mask = PDFAnnotation(bounds: maskRect, forType: .square, withProperties: nil)
    mask.color = .clear
    mask.interiorColor = NSColor(calibratedWhite: 1.0, alpha: 1.0)
    mask.border = PDFBorder()
    mask.border?.lineWidth = 0
    pageCopy.addAnnotation(mask)

    outDoc.insert(pageCopy, at: outDoc.pageCount)
}

if outDoc.write(to: URL(fileURLWithPath: outputPath)) {
    print("Wrote \(outputPath)")
    print("Pages: \(outDoc.pageCount)")
} else {
    fputs("Failed to write output PDF\n", stderr)
    exit(2)
}
