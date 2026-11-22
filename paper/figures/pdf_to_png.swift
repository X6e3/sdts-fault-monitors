// Renders page 1 of a PDF to a PNG on a white background (macOS).   swift pdf_to_png.swift IN.pdf OUT.png SCALE
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
let a = CommandLine.arguments
guard a.count == 4, let doc = CGPDFDocument(URL(fileURLWithPath: a[1]) as CFURL), let page = doc.page(at: 1),
      let scale = Double(a[3]) else { fatalError("usage: IN.pdf OUT.png SCALE") }
let box = page.getBoxRect(.cropBox)
let w = Int(box.width * scale), h = Int(box.height * scale)
let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                    space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
ctx.interpolationQuality = .high
ctx.scaleBy(x: scale, y: scale)
ctx.translateBy(x: -box.origin.x, y: -box.origin.y)
ctx.drawPDFPage(page)
let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: a[2]) as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, ctx.makeImage()!, nil)
guard CGImageDestinationFinalize(dest) else { fatalError("could not write \(a[2])") }
print("\(a[2]): \(w) x \(h) px")
