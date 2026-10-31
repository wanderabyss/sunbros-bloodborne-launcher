import QtQuick
import QtQuick.Shapes

// Line icons on a 24 × 24 grid, drawn at any size with the same stroke weight. The drawing code
// below is written against a 2D canvas context, but runs on a recorder that turns it into SVG
// paths; a Shape with the curve renderer draws them as vectors, sharp at any size, interface
// zoom (Theme.zoom) or display scaling.
Item {
    id: icon
    property string kind: "home"
    property color strokeColor: Theme.text
    property real stroke: 1.6
    width: 24
    height: 24
    readonly property var paths: build(kind)

    Shape {
        id: art
        width: 24; height: 24
        scale: Math.min(icon.width, icon.height) / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: icon.strokeColor
            strokeWidth: icon.stroke / Math.max(0.01, art.scale)
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: icon.paths.stroke }
        }
        ShapePath {
            strokeColor: "transparent"
            fillColor: icon.strokeColor
            PathSvg { path: icon.paths.fill }
        }
    }

    // Records canvas calls (moveTo, lineTo, curves, arc, ellipse, rect) as SVG path data.
    function build(kind) {
        let strokes = "", fills = "", cur = "", last = null
        const f = n => String(Math.round(n * 1000) / 1000)
        const pt = (x, y) => f(x) + " " + f(y)
        const go = (x, y) => { cur += (last ? "L" : "M") + pt(x, y) + " "; last = [x, y] }
        const c = {
            beginPath() { cur = ""; last = null },
            moveTo(x, y) { cur += "M" + pt(x, y) + " "; last = [x, y] },
            lineTo(x, y) { go(x, y) },
            closePath() { cur += "Z " },
            quadraticCurveTo(cx, cy, x, y) { cur += "Q" + pt(cx, cy) + " " + pt(x, y) + " "; last = [x, y] },
            bezierCurveTo(ax, ay, bx, by, x, y) { cur += "C" + pt(ax, ay) + " " + pt(bx, by) + " " + pt(x, y) + " "; last = [x, y] },
            arc(x, y, r, a0, a1, ccw) {
                go(x + r * Math.cos(a0), y + r * Math.sin(a0))
                let d = ccw ? a0 - a1 : a1 - a0
                const sweep = ccw ? 0 : 1
                if (d >= 2 * Math.PI - 1e-6) {
                    cur += "A" + f(r) + " " + f(r) + " 0 0 " + sweep + " " + pt(x - r * Math.cos(a0), y - r * Math.sin(a0)) + " "
                    cur += "A" + f(r) + " " + f(r) + " 0 0 " + sweep + " " + pt(x + r * Math.cos(a0), y + r * Math.sin(a0)) + " "
                    return
                }
                d = d % (2 * Math.PI); if (d < 0) d += 2 * Math.PI
                const a = ccw ? a0 - d : a0 + d
                last = [x + r * Math.cos(a), y + r * Math.sin(a)]
                cur += "A" + f(r) + " " + f(r) + " 0 " + (d > Math.PI ? 1 : 0) + " " + sweep + " " + pt(last[0], last[1]) + " "
            },
            ellipse(x, y, w, h) {
                const rx = w / 2, ry = h / 2, cx = x + rx, cy = y + ry
                cur += "M" + pt(cx - rx, cy) + " A" + f(rx) + " " + f(ry) + " 0 1 0 " + pt(cx + rx, cy)
                     + " A" + f(rx) + " " + f(ry) + " 0 1 0 " + pt(cx - rx, cy) + " Z "
                last = [cx - rx, cy]
            },
            rect(x, y, w, h) { cur += "M" + pt(x, y) + " H" + f(x + w) + " V" + f(y + h) + " H" + f(x) + " Z "; last = [x, y] },
            // A path is drawn once: what follows a stroke() starts again from its last point.
            stroke() { strokes += cur; cur = last ? "M" + pt(last[0], last[1]) + " " : "" },
            fill() { fills += cur; cur = last ? "M" + pt(last[0], last[1]) + " " : "" }
        }
        function line(p) { c.beginPath(); c.moveTo(p[0], p[1]); for (let i = 2; i < p.length; i += 2) c.lineTo(p[i], p[i + 1]); c.stroke() }
        function shape(p) { c.beginPath(); c.moveTo(p[0], p[1]); for (let i = 2; i < p.length; i += 2) c.lineTo(p[i], p[i + 1]); c.closePath(); c.stroke() }
        function circle(x, y, r) { c.beginPath(); c.arc(x, y, r, 0, 2 * Math.PI); c.stroke() }
        function dot(x, y, r) { c.beginPath(); c.arc(x, y, r, 0, 2 * Math.PI); c.fill() }
        function rect(x, y, w, h) { c.beginPath(); c.rect(x, y, w, h); c.stroke() }
        switch (kind) {
        case "huntersmark": // the Hunter's Mark: a stem, a slanted tick, an open diamond, a dot
            line([12, 1.2, 12, 21.4]); line([10.7, 3.7, 13.3, 2.9])
            line([12, 11.4, 7.0, 17.9]); line([12, 11.4, 17.0, 17.9])
            line([7.5, 19.1, 10.9, 22.0]); line([16.5, 19.1, 13.1, 22.0])
            dot(12, 22.9, 0.95); break
        case "hunter": // the guide's mark: a blade crossed with a compass rose
            line([12, 1.5, 12, 22.5]); line([3.5, 12, 20.5, 12])
            shape([12, 5, 15, 12, 12, 19, 9, 12]); line([9.5, 20, 12, 22.5, 14.5, 20]); break
        case "home":
            line([3, 11, 12, 3.5, 21, 11]); line([5, 9.5, 5, 21, 19, 21, 19, 9.5]); rect(10, 14.5, 4, 6.5); break
        case "play":
            shape([7, 4.5, 19, 12, 7, 19.5]); break
        case "settings": case "system": case "advanced":
            circle(12, 12, 3.2)
            for (let a = 0; a < 8; a++) { const t = a * Math.PI / 4; line([12 + 6.4 * Math.cos(t), 12 + 6.4 * Math.sin(t), 12 + 9 * Math.cos(t), 12 + 9 * Math.sin(t)]) }
            circle(12, 12, 6.4); break
        case "trophy": case "achievements":
            line([7, 3.5, 17, 3.5, 16.5, 11, 14, 14, 10, 14, 7.5, 11, 7, 3.5])
            line([7, 6, 3.5, 6, 4.5, 10, 7.6, 11.4]); line([17, 6, 20.5, 6, 19.5, 10, 16.4, 11.4])
            line([12, 14, 12, 18]); line([8, 20.5, 16, 20.5]); line([9.5, 18, 14.5, 18]); break
        case "character": case "profile":
            circle(8, 8, 3.5); line([4, 15.5, 12, 12, 20, 15.5, 20, 20]); line([4, 20, 20, 20]); break
        case "puzzle": case "mods": case "mods-and-patches": // a jigsaw piece with a knob on top and right
            c.beginPath(); c.moveTo(4, 7.5); c.lineTo(9.2, 7.5)
            c.bezierCurveTo(8.2, 5.8, 8.6, 3.5, 11, 3.5); c.bezierCurveTo(13.4, 3.5, 13.8, 5.8, 12.8, 7.5)
            c.lineTo(17.5, 7.5); c.lineTo(17.5, 11.7)
            c.bezierCurveTo(19.2, 10.7, 21.5, 11.1, 21.5, 13.5); c.bezierCurveTo(21.5, 15.9, 19.2, 16.3, 17.5, 15.3)
            c.lineTo(17.5, 20.5); c.lineTo(4, 20.5); c.closePath(); c.stroke(); break
        case "gpu": // a graphics card: the board, its fan, the bracket
            rect(4, 7, 17, 10); circle(10, 12, 3); line([15.5, 10, 18.5, 10]); line([15.5, 14, 18.5, 14])
            line([4, 5, 4, 20]); line([7, 17, 7, 19.5, 15, 19.5, 15, 17]); break
        case "cpu": // a processor: the package, its die and two pins a side
            rect(6, 6, 12, 12); rect(9.5, 9.5, 5, 5)
            for (const p of [10, 14]) { line([p, 3, p, 6]); line([p, 18, p, 21]); line([3, p, 6, p]); line([18, p, 21, p]) }
            break
        case "memory": // a memory module: the stick, three chips, its contacts
            rect(2.5, 7, 19, 9); rect(5, 9.5, 3.5, 4); rect(10.25, 9.5, 3.5, 4); rect(15.5, 9.5, 3.5, 4)
            line([5, 16, 5, 18.5]); line([9, 16, 9, 18.5]); line([15, 16, 15, 18.5]); line([19, 16, 19, 18.5]); break
        case "visuals": case "graphics": case "display":
            rect(2.5, 4, 19, 13); line([8.5, 21, 15.5, 21]); line([12, 17, 12, 21]); break
        case "controls": case "controller":
            c.beginPath(); c.moveTo(6.5, 7.5); c.lineTo(17.5, 7.5); c.quadraticCurveTo(21, 8.5, 22, 15)
            c.quadraticCurveTo(22.5, 20, 19, 19.5); c.lineTo(15.5, 16.5); c.lineTo(8.5, 16.5); c.lineTo(5, 19.5)
            c.quadraticCurveTo(1.5, 20, 2, 15); c.quadraticCurveTo(3, 8.5, 6.5, 7.5); c.stroke()
            line([6, 12, 10, 12]); line([8, 10, 8, 14]); dot(16, 11, 1); dot(18.5, 13.5, 1); break
        case "folder": case "game-and-saves":
            line([2.5, 6, 2.5, 19.5, 21.5, 19.5, 21.5, 8, 11, 8, 9, 5, 2.5, 5, 2.5, 6]); line([8.5, 13.5, 11, 16, 16, 11]); break
        case "online": case "globe":
            circle(12, 12, 9); line([3, 12, 21, 12])
            c.beginPath(); c.ellipse(8, 3, 8, 18); c.stroke(); break
        case "update":
            c.beginPath(); c.arc(12, 12, 8, -Math.PI * 0.35, Math.PI * 1.45); c.stroke()
            line([12, 7.5, 12, 15]); line([8.5, 12, 12, 15.5, 15.5, 12]); break
        case "chevron":
            line([9, 5, 16, 12, 9, 19]); break
        case "back":
            line([15, 5, 8, 12, 15, 19]); break
        case "search":
            circle(10.5, 10.5, 6); line([15, 15, 20.5, 20.5]); break
        case "log":
            rect(4.5, 2.5, 15, 19); line([8, 8, 16, 8]); line([8, 12, 16, 12]); line([8, 16, 13, 16]); break
        case "close":
            line([6, 6, 18, 18]); line([18, 6, 6, 18]); break
        case "eye":
            c.beginPath(); c.moveTo(2, 12); c.quadraticCurveTo(12, 1.5, 22, 12); c.quadraticCurveTo(12, 22.5, 2, 12); c.stroke()
            circle(12, 12, 3); break
        case "users":
            circle(9, 8, 3.5); line([2.5, 20, 2.5, 19]); c.beginPath(); c.moveTo(2.5, 20); c.quadraticCurveTo(3, 14, 9, 14); c.quadraticCurveTo(15, 14, 15.5, 20); c.stroke()
            c.beginPath(); c.arc(16, 8, 3.5, -Math.PI / 2, Math.PI / 2); c.stroke(); c.beginPath(); c.moveTo(18, 14.5); c.quadraticCurveTo(21.5, 15.5, 21.5, 20); c.stroke(); break
        case "coop":
            circle(7, 8, 3); circle(17, 8, 3)
            c.beginPath(); c.moveTo(2, 20); c.quadraticCurveTo(2, 14.5, 7, 14.5); c.quadraticCurveTo(12, 14.5, 12, 20); c.stroke()
            c.beginPath(); c.moveTo(12, 20); c.quadraticCurveTo(12, 14.5, 17, 14.5); c.quadraticCurveTo(22, 14.5, 22, 20); c.stroke(); break
        case "wrench":
            line([14.7, 6.3, 12.2, 8.8, 12.8, 11.2, 15.2, 11.8, 17.7, 9.3])
            c.beginPath(); c.moveTo(17.7, 9.3); c.bezierCurveTo(19, 6, 17, 3, 14.7, 3.6); c.lineTo(14.7, 6.3); c.stroke()
            line([12.2, 8.8, 3.5, 17.5, 6.5, 20.5, 15.2, 11.8]); break
        case "sliders":
            line([4, 6, 14, 6]); line([18, 6, 20, 6]); circle(16, 6, 2)
            line([4, 12, 8, 12]); line([12, 12, 20, 12]); circle(10, 12, 2)
            line([4, 18, 16, 18]); circle(18, 18, 2); break
        case "star":
            shape([12, 2.5, 14.6, 9, 21.5, 9.4, 16.2, 13.8, 17.9, 20.6, 12, 16.9, 6.1, 20.6, 7.8, 13.8, 2.5, 9.4, 9.4, 9]); break
        case "map":
            shape([3, 6, 9, 4, 15, 6, 21, 4, 21, 18, 15, 20, 9, 18, 3, 20]); line([9, 4, 9, 18]); line([15, 6, 15, 20]); break
        case "file": case "patch":
            line([14, 3, 14, 8, 19, 8]); shape([6, 3, 14, 3, 19, 8, 19, 21, 6, 21]); break
        case "bolt": case "fps":
            shape([13, 2, 4, 14, 11, 14, 10, 22, 19, 10, 12, 10]); break
        case "layers": case "framegen":
            rect(4, 6, 10, 10); rect(10, 10, 10, 10); break
        case "upscale":
            line([15, 3, 21, 3, 21, 9]); line([9, 21, 3, 21, 3, 15]); line([21, 3, 14, 10]); line([3, 21, 10, 14]); break
        case "sun": case "hdr":
            circle(12, 12, 4)
            for (let b = 0; b < 8; b++) { const u = b * Math.PI / 4; line([12 + 6.5 * Math.cos(u), 12 + 6.5 * Math.sin(u), 12 + 9 * Math.cos(u), 12 + 9 * Math.sin(u)]) }
            break
        case "download": case "saves":
            line([12, 3, 12, 15]); line([7, 10, 12, 15, 17, 10]); line([4, 20, 20, 20]); break
        case "language":
            circle(12, 12, 9); line([3, 12, 21, 12]); line([12, 3, 12, 21]); break
        case "power":
            line([12, 3, 12, 12]); c.beginPath(); c.arc(12, 13, 7.5, -Math.PI * 0.3, Math.PI * 1.3); c.stroke(); break
        case "sparkle": case "neural":
            shape([12, 3, 13.8, 10.2, 21, 12, 13.8, 13.8, 12, 21, 10.2, 13.8, 3, 12, 10.2, 10.2]); break
        case "image": case "texture":
            rect(3, 4, 18, 16); circle(9, 9.5, 1.8); line([3, 17, 9, 12, 14, 16, 17, 13, 21, 17]); break
        case "check": case "done":
            line([5, 12.5, 10, 17.5, 19.5, 7]); break
        case "alert": // ! in a circle
            circle(12, 12, 9); line([12, 7.5, 12, 13]); dot(12, 16.5, 1.2); break
        case "plus":
            line([12, 5, 12, 19]); line([5, 12, 19, 12]); break
        default:
            circle(12, 12, 8)
        }
        return {stroke: strokes, fill: fills}
    }
}
