// Encode a directory of numbered PNG frames into an H.264 MP4.
// Used by videoify.py; frames are fed in playback order (bounce included).
//
//   swiftc -O scripts/png2mp4.swift -o png2mp4
//   ./png2mp4 <frames-dir> <out.mp4> <fps> [bitsPerPixel=0.12]

import AVFoundation
import AppKit

let args = CommandLine.arguments
guard args.count >= 4 else {
    FileHandle.standardError.write("usage: png2mp4 <frames-dir> <out.mp4> <fps> [bpp]\n".data(using: .utf8)!)
    exit(2)
}
let framesDir = args[1]
let outPath = args[2]
let fps = Int32(args[3]) ?? 20
let bpp = args.count > 4 ? Double(args[4]) ?? 0.12 : 0.12

let fm = FileManager.default
let files = try! fm.contentsOfDirectory(atPath: framesDir)
    .filter { $0.hasSuffix(".png") }
    .sorted()
guard let first = NSImage(contentsOfFile: framesDir + "/" + files[0]),
      let firstRep = first.representations.first else {
    FileHandle.standardError.write("cannot read first frame\n".data(using: .utf8)!)
    exit(1)
}
let width = firstRep.pixelsWide - (firstRep.pixelsWide % 2)
let height = firstRep.pixelsHigh - (firstRep.pixelsHigh % 2)

try? fm.removeItem(atPath: outPath)
let writer = try! AVAssetWriter(outputURL: URL(fileURLWithPath: outPath), fileType: .mp4)
let bitrate = max(600_000, Int(Double(width * height) * Double(fps) * bpp))
let settings: [String: Any] = [
    AVVideoCodecKey: AVVideoCodecType.h264,
    AVVideoWidthKey: width,
    AVVideoHeightKey: height,
    AVVideoCompressionPropertiesKey: [
        AVVideoAverageBitRateKey: bitrate,
        AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
    ],
]
let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
input.expectsMediaDataInRealTime = false
let adaptor = AVAssetWriterInputPixelBufferAdaptor(
    assetWriterInput: input,
    sourcePixelBufferAttributes: [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB,
        kCVPixelBufferWidthKey as String: width,
        kCVPixelBufferHeightKey as String: height,
    ])
writer.add(input)
writer.startWriting()
writer.startSession(atSourceTime: .zero)

func pixelBuffer(from image: NSImage) -> CVPixelBuffer? {
    var pb: CVPixelBuffer?
    guard CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &pb) == kCVReturnSuccess,
          let buf = pb else { return nil }
    CVPixelBufferLockBaseAddress(buf, [])
    defer { CVPixelBufferUnlockBaseAddress(buf, []) }
    let ctx = CGContext(
        data: CVPixelBufferGetBaseAddress(buf),
        width: width, height: height, bitsPerComponent: 8,
        bytesPerRow: CVPixelBufferGetBytesPerRow(buf),
        space: CGColorSpace(name: CGColorSpace.sRGB)!,
        bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue)!
    var rect = CGRect(x: 0, y: 0, width: width, height: height)
    guard let cg = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) else { return nil }
    ctx.draw(cg, in: rect)
    return buf
}

var i: Int64 = 0
for f in files {
    guard let img = NSImage(contentsOfFile: framesDir + "/" + f),
          let buf = pixelBuffer(from: img) else { continue }
    while !input.isReadyForMoreMediaData { usleep(2000) }
    adaptor.append(buf, withPresentationTime: CMTime(value: i, timescale: fps))
    i += 1
}
input.markAsFinished()
let sema = DispatchSemaphore(value: 0)
writer.finishWriting { sema.signal() }
sema.wait()
print("wrote \(outPath): \(i) frames \(width)x\(height) @\(fps)fps ~\(bitrate/1000)kbps")
