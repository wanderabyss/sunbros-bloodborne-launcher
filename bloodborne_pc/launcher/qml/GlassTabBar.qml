import QtQuick
import QtQuick.Controls

// The floating glass tab bar shared by every page (not first-time setup): a fully round pill
// with no top highlight line, and one highlight that slides to the current tab.
GlassPanel {
    id: bar
    objectName: "primaryNavigation"
    property string current: "Home"
    signal navigate(string destination)
    readonly property var tabs: [
        {key: "Home", title: "Home", icon: "home"},
        {key: "Visuals", title: "Visuals", icon: "eye"},
        {key: "Online", title: "Online", icon: "users"},
        {key: "Coop", title: "Co-op", icon: "coop"},
        {key: "Dossier", title: "Dossier", icon: "trophy"},
        {key: "Mods", title: "Workshop", icon: "wrench"},
        {key: "Settings", title: "Settings", icon: "settings"}
    ]
    width: 640; height: Theme.tabBarHeight
    radius: height / 2
    highlight: false
    readonly property int currentIndex: tabs.findIndex(t => t.key === current)
    readonly property real tabWidth: (bar.width - 12 - 2 * (bar.tabs.length - 1)) / bar.tabs.length
    Rectangle {
        objectName: "tabHighlight"
        visible: bar.currentIndex >= 0
        x: 6 + Math.max(0, bar.currentIndex) * (bar.tabWidth + 2); y: 6
        width: bar.tabWidth; height: bar.height - 12
        radius: height / 2
        color: "#38ffffff"
        Behavior on x { NumberAnimation { duration: Theme.reducedMotion ? 0 : 260; easing.type: Easing.OutBack; easing.overshoot: 0.6 } }
    }
    Row {
        anchors.fill: parent; anchors.margins: 6; spacing: 2
        Repeater {
            model: bar.tabs
            delegate: Button {
                id: tab
                required property var modelData
                required property int index
                readonly property bool active: bar.current === modelData.key
                objectName: "primary_" + modelData.key
                width: bar.tabWidth
                height: parent.height
                hoverEnabled: true
                Accessible.name: modelData.title + (active ? ", current page" : "")
                ToolTip.visible: hovered && !active
                ToolTip.delay: 700
                ToolTip.text: modelData.title + "  (Ctrl+" + (index + 1) + ")"
                onClicked: bar.navigate(modelData.key)
                contentItem: Item { Column {
                    anchors.centerIn: parent
                    spacing: 3
                    NavIcon {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 21; height: 21; kind: tab.modelData.icon; stroke: 1.8
                        scale: tab.down ? 0.9 : tab.active ? 1.06 : 1
                        Behavior on scale { NumberAnimation { duration: Theme.motionFast; easing.type: Easing.OutCubic } }
                        strokeColor: tab.active || tab.hovered ? Theme.text : Theme.textDim
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: tab.modelData.title
                        color: tab.active || tab.hovered ? Theme.text : Theme.textDim
                        font.family: Theme.sans; font.pixelSize: 12; font.weight: Font.DemiBold
                    }
                } }
                background: Rectangle {
                    radius: height / 2
                    color: !tab.active && tab.hovered ? "#1affffff" : "transparent"
                    border.color: tab.visualFocus ? Theme.lineFocus : "transparent"
                    border.width: 2
                    Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                }
            }
        }
    }
}
