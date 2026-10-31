import QtQuick
import QtQuick.Controls

Item {
    signal backRequested()

    // Background
    Image {
        anchors.fill: parent
        source: Qt.resolvedUrl("../assets/ui/home-bg.jpg")
        fillMode: Image.PreserveAspectCrop
        opacity: 0.85
    }

    Rectangle { anchors.fill: parent; color: Theme.base; opacity: 0.2 }

    // Header
    Rectangle {
        width: parent.width
        height: 60
        color: Theme.surface
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: Theme.line
        }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            text: "HUNTER'S PROFILE"
            color: Theme.text
            font.family: Theme.serif
            font.pixelSize: 14
            font.weight: Font.Bold
            font.letterSpacing: 1
        }
    }

    // Content
    Flickable {
        anchors.top: parent.top
        anchors.topMargin: 60
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 40
        contentHeight: column.implicitHeight + 40
        clip: true

        Column {
            id: column
            width: parent.width
            spacing: 24

            // No save data message
            Rectangle {
                visible: !launcher.profileData
                width: parent.width
                height: 120
                radius: Theme.radius
                color: Theme.surface
                border.width: 1
                border.color: Theme.line

                Column {
                    anchors.centerIn: parent
                    anchors.margins: 20
                    spacing: 8

                    Text {
                        text: "No save data found"
                        color: Theme.text
                        font.family: Theme.serif
                        font.pixelSize: 18
                        font.weight: Font.Bold
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: "Launch the game to create a character"
                        color: Theme.textDim
                        font.family: Theme.sans
                        font.pixelSize: 12
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }

            // Hunter info (if data exists)
            Rectangle {
                visible: launcher.profileData
                width: parent.width
                height: 140
                radius: Theme.radius
                color: Theme.surfaceActive
                border.width: 1
                border.color: Theme.lineFocus

                Column {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 16

                    Row {
                        spacing: 40
                        width: parent.width

                        Column {
                            spacing: 4
                            Text {
                                text: "HUNTER"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                font.letterSpacing: 1
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.name : "—"
                                color: Theme.text
                                font.family: Theme.serif
                                font.pixelSize: 26
                                font.weight: Font.Bold
                            }
                        }

                        Column {
                            spacing: 4
                            Text {
                                text: "LEVEL"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                font.letterSpacing: 1
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.level.toString() : "—"
                                color: Theme.accent
                                font.family: Theme.serif
                                font.pixelSize: 26
                                font.weight: Font.Bold
                            }
                        }

                        Column {
                            spacing: 4
                            Text {
                                text: "PLAYTIME"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                                font.weight: Font.Bold
                                font.letterSpacing: 1
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.play_time : "—"
                                color: Theme.good
                                font.family: Theme.sans
                                font.pixelSize: 14
                                font.weight: Font.Bold
                            }
                        }
                    }
                }
            }

            // Stats grid
            Rectangle {
                visible: launcher.profileData
                width: parent.width
                height: statsColumn.implicitHeight + 40
                radius: Theme.radius
                color: Theme.surfaceActive
                border.width: 1
                border.color: Theme.lineFocus

                Column {
                    id: statsColumn
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 16

                    Text {
                        text: "ATTRIBUTES"
                        color: Theme.textFaint
                        font.family: Theme.sans
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        font.letterSpacing: 1
                    }

                    Grid {
                        columns: 3
                        spacing: 20
                        width: parent.width

                        Column {
                            spacing: 4
                            Text {
                                text: "Vitality"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.vitality.toString() : "—"
                                color: Theme.text
                                font.family: Theme.serif
                                font.pixelSize: 18
                                font.weight: Font.Bold
                            }
                        }

                        Column {
                            spacing: 4
                            Text {
                                text: "Endurance"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.endurance.toString() : "—"
                                color: Theme.text
                                font.family: Theme.serif
                                font.pixelSize: 18
                                font.weight: Font.Bold
                            }
                        }

                        Column {
                            spacing: 4
                            Text {
                                text: "Strength"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.strength.toString() : "—"
                                color: Theme.text
                                font.family: Theme.serif
                                font.pixelSize: 18
                                font.weight: Font.Bold
                            }
                        }

                        Column {
                            spacing: 4
                            Text {
                                text: "Skill"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.skill.toString() : "—"
                                color: Theme.text
                                font.family: Theme.serif
                                font.pixelSize: 18
                                font.weight: Font.Bold
                            }
                        }

                        Column {
                            spacing: 4
                            Text {
                                text: "Bloodtinge"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.bloodtinge.toString() : "—"
                                color: Theme.text
                                font.family: Theme.serif
                                font.pixelSize: 18
                                font.weight: Font.Bold
                            }
                        }

                        Column {
                            spacing: 4
                            Text {
                                text: "Arcane"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.arcane.toString() : "—"
                                color: Theme.text
                                font.family: Theme.serif
                                font.pixelSize: 18
                                font.weight: Font.Bold
                            }
                        }
                    }
                }
            }

            // Progress stats
            Rectangle {
                visible: launcher.profileData
                width: parent.width
                height: progColumn.implicitHeight + 40
                radius: Theme.radius
                color: Theme.surfaceActive
                border.width: 1
                border.color: Theme.lineFocus

                Column {
                    id: progColumn
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 16

                    Text {
                        text: "PROGRESS"
                        color: Theme.textFaint
                        font.family: Theme.sans
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        font.letterSpacing: 1
                    }

                    Row {
                        spacing: 40
                        width: parent.width

                        Column {
                            spacing: 4
                            Text {
                                text: "Blood Echoes"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.blood_echoes.toString() : "0"
                                color: Theme.info
                                font.family: Theme.sans
                                font.pixelSize: 14
                                font.weight: Font.Bold
                            }
                        }

                        Column {
                            spacing: 4
                            Text {
                                text: "Insight"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.insight.toString() : "0"
                                color: Theme.warn
                                font.family: Theme.sans
                                font.pixelSize: 14
                                font.weight: Font.Bold
                            }
                        }

                        Column {
                            spacing: 4
                            Text {
                                text: "Deaths"
                                color: Theme.textFaint
                                font.family: Theme.sans
                                font.pixelSize: 10
                            }
                            Text {
                                text: launcher.profileData ? launcher.profileData.deaths.toString() : "0"
                                color: Theme.error
                                font.family: Theme.sans
                                font.pixelSize: 14
                                font.weight: Font.Bold
                            }
                        }
                    }
                }
            }
        }
    }

    // Back button (bottom-left)
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.margins: 20
        width: 44
        height: 44
        radius: 4
        color: Theme.surfaceActive
        border.width: 1
        border.color: Theme.lineFocus

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: backRequested()
            onEntered: parent.color = Theme.surfaceHover
            onExited: parent.color = Theme.surfaceActive
        }

        Text {
            anchors.centerIn: parent
            text: "←"
            color: Theme.text
            font.pixelSize: 20
            font.weight: Font.Bold
        }
    }
}
