pragma Singleton
import QtQuick

// Glass theme: frosted panels over pre-blurred Bloodborne art (docs/design/launcher-glass).
// The older names (surface, line, accent...) stay so every control keeps compiling; their
// values are the glass ones.
QtObject {
    property bool reducedMotion: false // Session-only visual preference.
    // How much Main.qml magnifies the whole interface: 1 at the design size (1290 x 830), more
    // when the window is larger (a maximised 4K window) or the player picks a size in Settings.
    // Canvas icons read it to paint at the magnified resolution and stay sharp.
    property real zoom: 1
    // Any page asks Main.qml to show release notes: "update" (the offered release) or "whatsnew".
    signal showReleaseNotes(string mode)
    // Interface size (A− / A+), saved as ui_scale: a step around the fitted size, "auto" = 100%.
    // Controls set it here and save it with launcher.setValue (which emits no change signal).
    property string uiScale: "auto"
    readonly property var sizeSteps: [0.8, 0.9, 1, 1.1, 1.2, 1.3]
    readonly property real sizeStep: sizeSteps[sizeIndex(uiScale)]
    function sizeIndex(saved) {
        var n = saved === "auto" ? 1 : Number(saved)
        if (!isFinite(n) || n <= 0) n = 1
        var best = 2
        for (var i = 0; i < sizeSteps.length; i++)
            if (Math.abs(sizeSteps[i] - n) < Math.abs(sizeSteps[best] - n)) best = i
        return best
    }
    function sizeValue(index) {
        var step = sizeSteps[Math.max(0, Math.min(sizeSteps.length - 1, index))]
        return step === 1 ? "auto" : String(step)
    }
    readonly property int motionFast: reducedMotion ? 0 : 140
    readonly property int motionPage: reducedMotion ? 0 : 240

    // Behind everything, where no art is shown.
    readonly property color base: "#14161c"
    readonly property color panel: "#26ffffff"

    // Glass: a light translucent fill over the blurred art.
    readonly property color glassTop: "#2effffff"
    readonly property color glassBottom: "#12ffffff"
    readonly property color glassEdge: "#38ffffff"
    readonly property color smokeTop: "#5c1a1d24"       // darker glass over bright art
    readonly property color smokeBottom: "#7a101217"
    readonly property color glassHighlight: "#59ffffff"
    readonly property color well: "#2e000000"          // rows inside glass
    readonly property color surface: "#1fffffff"       // a control at rest
    readonly property color surfaceHover: "#30ffffff"
    readonly property color surfaceActive: "#40ffffff"
    readonly property color selection: "#38ffffff"

    // Lines
    readonly property color line: "#1fffffff"
    readonly property color lineStrong: "#38ffffff"
    readonly property color lineFocus: "#ffffff"

    // Text
    readonly property color text: "#ffffff"
    readonly property color textDim: "#c7ffffff"
    readonly property color textFaint: "#bfffffff"
    readonly property color textMuted: "#8cffffff"

    readonly property color gold: "#ffd27a"            // SunBro's Edition
    readonly property color brass: "#ffd27a"
    readonly property color data: "#ffffff"

    // The primary action is a white pill; red is kept for errors and progress.
    readonly property color primary: "#ffffff"
    readonly property color primaryText: "#000000"
    readonly property color accent: "#ff6b62"
    readonly property color accentHover: "#ff8a80"
    readonly property color accentActive: "#ff9d95"
    readonly property color accentSoft: "#40ff6b62"
    readonly property color link: "#8cc8ff"

    // Status
    readonly property color good: "#30d158"
    readonly property color goodText: "#7ef09a"
    readonly property color warn: "#ffd60a"
    readonly property color info: "#8cc8ff"
    readonly property color error: "#ff8a80"

    // Typography: Segoe UI Variable stands in for SF Pro; the Bloodborne face is for the logo.
    readonly property string bloodborne: "fleshandblood"
    readonly property string serif: "fleshandblood"
    readonly property string sans: "Segoe UI Variable Display"
    readonly property int fontSmall: 12
    readonly property int fontNormal: 14
    readonly property int fontLarge: 15
    readonly property int fontHuge: 20

    // Layout
    readonly property int railWidth: 0
    readonly property int radius: 12
    readonly property int radiusSmall: 8
    readonly property int radiusCard: 28
    readonly property int rowHeight: 50
    readonly property int spacing: 12
    readonly property int spacingLarge: 20
    readonly property int pageTop: 48
    readonly property int columnWidth: 720
    readonly property int tabBarHeight: 64
    readonly property int tabBarBottom: 28
}
