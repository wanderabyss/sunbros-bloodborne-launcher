import QtQuick
import QtQuick.Controls

// One setting in a glass list: label (and a smaller second line) on the left, its control on
// the right, a hairline below.
Item {
    id: fieldRow
    property var field: ({})
    property string settingKey: field.key || ""
    property bool hasHint: (field.hint || "") !== ""
    property bool isFolder: field.kind === "folder" || field.kind === "file"
    property real controlWidth: Math.min(340, width * 0.48)
    // Not offered here (the backend says why in the hint): shown, not changeable.
    enabled: !(field.disabled || false)
    opacity: enabled ? 1.0 : 0.5
    implicitHeight: isFolder ? (labels.y + labels.height + 8 + 36 + 12) : Math.max(52, labels.implicitHeight + 24)
    height: implicitHeight

    Column {
        id: labels
        x: 16
        y: isFolder ? 12 : (parent.height - height) / 2
        width: isFolder ? parent.width - 32 : parent.width - fieldRow.controlWidth - 48
        spacing: 2
        Text {
            width: parent.width; text: field.label || ""; color: Theme.text; elide: Text.ElideRight
            font.family: Theme.sans; font.pixelSize: 15
        }
        Text {
            visible: hasHint; width: parent.width; text: field.hint || ""; color: Theme.textFaint
            font.family: Theme.sans; font.pixelSize: 12; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
        }
    }
    GlassSwitch {
        visible: field.kind === "toggle"
        enabled: field.enabled !== false
        anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
        checked: launcher.checked(settingKey)
        onToggled: launcher.setValue(settingKey, checked)
    }
    GlassComboBox {
        visible: field.kind === "choice"
        anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
        width: fieldRow.controlWidth; height: 36
        model: field.options || []
        textRole: "text"
        valueRole: "value"
        Component.onCompleted: currentIndex = indexOfValue(String(launcher.value(settingKey)))
        onActivated: launcher.setValue(settingKey, currentValue)
    }
    GlassTextField {
        id: valueInput
        visible: field.kind !== "toggle" && field.kind !== "choice"
        x: isFolder ? 16 : parent.width - width - 12
        y: isFolder ? (labels.y + labels.height + 8) : (parent.height - height) / 2
        width: isFolder ? parent.width - 32 - 108 : fieldRow.controlWidth
        height: 36
        text: String(launcher.value(settingKey))
        placeholderText: isFolder ? "Default location" : ""
        echoMode: field.kind === "password" ? TextInput.Password : TextInput.Normal
        // Saved as it is typed or pasted: a page change destroys the field before it loses
        // focus, and a pasted co-op invite code was lost that way.
        onTextEdited: launcher.setValue(settingKey, text)
        onEditingFinished: launcher.setValue(settingKey, text)
    }
    Connections {
        target: launcher
        function onChanged() {
            if (valueInput.visible && !valueInput.activeFocus) {
                valueInput.text = String(launcher.value(settingKey))
            }
        }
    }
    GlassButton {
        visible: isFolder
        text: "Browse"
        anchors.right: parent.right; anchors.rightMargin: 12; y: valueInput.y; height: 36; width: 96
        onClicked: launcher.browse(settingKey)
    }
    Rectangle { x: 16; anchors.bottom: parent.bottom; width: parent.width - 16; height: 1; color: Theme.line }
}
