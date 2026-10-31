import QtQuick

// A glass card. `tiltEnabled` and the colour properties stay for older callers; the card is flat.
GlassPanel {
    id: card
    default property alias contentData: content.data
    property color fillColor: Theme.glassBottom
    property color edgeColor: Theme.glassEdge
    property bool tiltEnabled: false
    readonly property bool hovered: pointer.hovered
    radius: 22
    border.color: card.edgeColor
    Item { id: content; anchors.fill: parent }
    HoverHandler { id: pointer }
}
