import QtQuick

// Frosted glass over the page's pre-blurred art: a light gradient, a hairline edge and an inner
// top highlight. The art behind is already blurred, so nothing is blurred live. `smoked` darkens
// the glass for a panel over bright art (Home's sky), where white text loses contrast.
// No top highlight line by default: the user wants plain round glass (tab bar, Play panel, cards).
Rectangle {
    id: panel
    property bool smoked: false
    property bool highlight: false
    radius: Theme.radiusCard
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
