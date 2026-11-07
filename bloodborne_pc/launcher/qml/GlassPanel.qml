import QtQuick
import QtQuick.Effects

// Frosted glass: a light gradient, a hairline edge, and over Home's sharp art `frost`, which blurs the
// art behind the panel, live and at half resolution (the art does not change, so it costs little). A
// panel inside a frosted panel has nothing to add and skips it. `smoked` darkens the glass for a panel over bright art
// (Home's sky), where white text loses contrast.
// No top highlight line by default: the user wants plain round glass (tab bar, Play panel, cards).
Rectangle {
    id: panel
    property bool smoked: false
    property bool highlight: false
    property bool frost: true
    readonly property bool frosting: frost && !nested
    property bool nested: false
    Component.onCompleted: {
        for (let item = parent; item; item = item.parent) {
            if (item.frosting === true) {
                nested = true
                break
            }
        }
    }
    radius: Theme.radiusCard
    // Behind the gradient. Not on the software renderer, which has no shader effects.
    Loader {
        anchors.fill: parent
        z: -1
        active: panel.frosting && panel.visible && Theme.backdrop !== null && Theme.sharpBackdrop
                && GraphicsInfo.api !== GraphicsInfo.Software
        sourceComponent: Item {
            // What the panel covers. Its layout parents do not report moves: Theme.frostTick does.
            readonly property rect behind: {
                Theme.frostTick; panel.x; panel.y; panel.width; panel.height
                return panel.mapToItem(Theme.backdrop, 0, 0, panel.width, panel.height)
            }
            ShaderEffectSource {
                id: art
                sourceItem: Theme.backdrop
                sourceRect: parent.behind
                textureSize: Qt.size(Math.max(1, Math.ceil(parent.behind.width / 2)),
                                     Math.max(1, Math.ceil(parent.behind.height / 2)))
                visible: false
            }
            Rectangle {
                id: shape
                width: panel.width; height: panel.height
                radius: panel.radius
                visible: false
                layer.enabled: true
            }
            MultiEffect {
                width: panel.width; height: panel.height
                source: art
                autoPaddingEnabled: false
                blurEnabled: true
                blur: 1
                blurMax: 40
                saturation: 0.12
                maskEnabled: true
                maskSource: shape
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1
            }
        }
    }
    gradient: Gradient {
        GradientStop { position: 0; color: panel.smoked ? Theme.smokeTop : Theme.glassTop }
        GradientStop { position: 1; color: panel.smoked ? Theme.smokeBottom : Theme.glassBottom }
    }
    border.color: Theme.glassEdge
    border.width: 1
    Rectangle {
        visible: panel.highlight
        x: Math.min(panel.radius * 0.7, panel.width / 4); y: 1
        width: panel.width - 2 * x; height: 1
        color: Theme.glassHighlight
    }
}
