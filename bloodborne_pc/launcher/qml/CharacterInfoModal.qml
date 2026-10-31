import QtQuick
import QtQuick.Controls

Rectangle {
    id: modal
    anchors.fill: parent
    property bool fullPage: false
    color: fullPage ? Theme.base : "#cc06080b"
    visible: false

    signal closeRequested()

    property string lockedCategory: "All"
    property string searchQuery: ""

    onVisibleChanged: {
        if (visible) {
            launcher.refresh_profile_data()
            lockedCategory = "All"
            searchQuery = ""
        }
    }

    function gradeColor(grade) {
        if (grade === "P") return "#5dd3f3"
        if (grade === "G") return "#f5c342"
        if (grade === "S") return "#d4dbe2"
        return "#cd7f32"
    }

    function gradeBg(grade) {
        if (grade === "P") return "#162e38"
        if (grade === "G") return "#2e2410"
        if (grade === "S") return "#22272e"
        return "#2b1c14"
    }

    function filterTrophies(list, cat, query) {
        if (!list) return []
        var q = (query || "").toLowerCase().trim()
        return list.filter(function(item) {
            if (cat !== "All" && item.category !== cat) return false
            if (q !== "") {
                var n = (item.name || "").toLowerCase()
                var d = (item.description || "").toLowerCase()
                if (n.indexOf(q) === -1 && d.indexOf(q) === -1) return false
            }
            return true
        })
    }

    // Dismiss modal on backdrop click
    MouseArea {
        anchors.fill: parent
        onClicked: modal.closeRequested()
    }

    // Modal Dialog Window
    Rectangle {
        id: card
        anchors.centerIn: parent
        width: modal.fullPage ? Math.min(parent.width - 72, 1320) : Math.min(parent.width - 32, 1140)
        height: modal.fullPage ? parent.height - 32 : Math.min(parent.height - 32, 720)
        radius: 12
        color: "#0a0c11"
        border.width: 1
        border.color: "#2b3445"
        clip: true

        MouseArea {
            anchors.fill: parent
            onClicked: {} // Absorb clicks inside card
        }

        // Inner glowing border / vignette accent
        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: 11
            color: "transparent"
            border.width: 1
            border.color: "#161b24"
        }

        Column {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // ==========================================================
            // HEADER BAR
            // ==========================================================
            Row {
                width: parent.width
                height: 32

                Row {
                    spacing: 12
                    anchors.verticalCenter: parent.verticalCenter

                    Image {
                        source: launcher.userAvatar || Qt.resolvedUrl("../assets/ui/sunbros-avatar.png")
                        cache: false
                        width: 24
                        height: 24
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        mipmap: true
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Text {
                        text: "HUNTER'S DOSSIER & TROPHIES"
                        color: "#f0ede7"
                        font.family: Theme.serif
                        font.pixelSize: 17
                        font.weight: Font.Bold
                        font.letterSpacing: 2.0
                    }

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 8
                        height: 8
                        radius: 4
                        color: launcher.profileData && launcher.profileData.valid ? Theme.good : Theme.error
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: {
                            if (!launcher.profileData || !launcher.profileData.valid) return "No save data detected"
                            return "Active Hunter: " + (launcher.profileData.name || "Hunter") + "  ·  Slot 1"
                        }
                        color: Theme.textDim
                        font.family: Theme.sans
                        font.pixelSize: 11
                    }
                }

                Item { width: 1; height: 1 }

                // Close Button
                Rectangle {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: 30
                    height: 30
                    radius: 6
                    color: closeHit.containsMouse ? "#3a181e" : "#141720"
                    border.width: 1
                    border.color: closeHit.containsMouse ? Theme.accent : "#242c3b"

                    Text {
                        anchors.centerIn: parent
                        text: "x"
                        color: closeHit.containsMouse ? "#ff6b75" : Theme.textDim
                        font.pixelSize: 13
                        font.weight: Font.Bold
                    }

                    MouseArea {
                        id: closeHit
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: modal.closeRequested()
                    }
                }
            }

            // ==========================================================
            // TOP HUNTER OVERVIEW BANNER (When Save Exists)
            // ==========================================================
            Rectangle {
                visible: launcher.profileData && launcher.profileData.valid
                width: parent.width
                height: 98
                radius: 8
                color: "#10141c"
                border.width: 1
                border.color: "#222a38"

                Row {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 12

                    // 1. Identity Tile
                    Rectangle {
                        width: 160
                        height: parent.height
                        color: "#0a0d13"
                        radius: 6
                        border.width: 1
                        border.color: "#1c2330"

                        Column {
                            anchors.centerIn: parent
                            spacing: 4

                            Text {
                                text: launcher.profileData && launcher.profileData.name ? launcher.profileData.name : "Hunter"
                                color: "#f0ede7"
                                font.family: Theme.serif
                                font.pixelSize: 18
                                font.weight: Font.Bold
                                elide: Text.ElideRight
                                width: 144
                                horizontalAlignment: Text.AlignHCenter
                            }

                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                height: 20
                                width: lvlText.implicitWidth + 14
                                radius: 10
                                color: "#301318"
                                border.width: 1
                                border.color: "#6b222a"

                                Text {
                                    id: lvlText
                                    anchors.centerIn: parent
                                    text: "LEVEL " + (launcher.profileData && launcher.profileData.level !== undefined ? launcher.profileData.level.toString() : "—")
                                    color: "#ff636f"
                                    font.family: Theme.serif
                                    font.pixelSize: 11
                                    font.weight: Font.Bold
                                    font.letterSpacing: 0.8
                                }
                            }

                            Row {
                                anchors.horizontalCenter: parent.horizontalCenter
                                spacing: 4
                                Text { text: "⏱"; font.pixelSize: 10 }
                                Text {
                                    text: launcher.profileData && launcher.profileData.play_time ? launcher.profileData.play_time : "—"
                                    color: Theme.textDim
                                    font.family: Theme.sans
                                    font.pixelSize: 11
                                }
                            }
                        }
                    }

                    // 2. Attributes Micro-Tiles
                    Column {
                        width: 410
                        height: parent.height
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 4

                        Text {
                            text: "COMBAT ATTRIBUTES"
                            color: Theme.textFaint
                            font.family: Theme.sans
                            font.pixelSize: 9
                            font.weight: Font.Bold
                            font.letterSpacing: 1.2
                        }

                        Row {
                            spacing: 6
                            width: parent.width

                            Repeater {
                                model: [
                                    {label: "VIT", val: launcher.profileData ? launcher.profileData.vitality : "—"},
                                    {label: "END", val: launcher.profileData ? launcher.profileData.endurance : "—"},
                                    {label: "STR", val: launcher.profileData ? launcher.profileData.strength : "—"},
                                    {label: "SKL", val: launcher.profileData ? launcher.profileData.skill : "—"},
                                    {label: "BLT", val: launcher.profileData ? launcher.profileData.bloodtinge : "—"},
                                    {label: "ARC", val: launcher.profileData ? launcher.profileData.arcane : "—"}
                                ]
                                delegate: Rectangle {
                                    width: 63
                                    height: 52
                                    radius: 6
                                    color: "#0a0d13"
                                    border.width: 1
                                    border.color: "#1c2330"

                                    Column {
                                        anchors.centerIn: parent
                                        spacing: 2
                                        Text {
                                            text: modelData.label
                                            color: Theme.textFaint
                                            font.family: Theme.sans
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            anchors.horizontalCenter: parent.horizontalCenter
                                        }
                                        Text {
                                            text: modelData.val
                                            color: "#f0ede7"
                                            font.family: Theme.serif
                                            font.pixelSize: 16
                                            font.weight: Font.Bold
                                            anchors.horizontalCenter: parent.horizontalCenter
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: 1
                        height: parent.height - 12
                        anchors.verticalCenter: parent.verticalCenter
                        color: "#1e2636"
                    }

                    // 3. Resources & Tallies (Echoes, Insight, Deaths, Trophies)
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 8

                        Repeater {
                            model: [
                                {
                                    icon: "",
                                    title: "Blood Echoes",
                                    val: launcher.profileData && launcher.profileData.blood_echoes !== undefined ? launcher.profileData.blood_echoes.toLocaleString() : "0",
                                    col: "#6fb5d9"
                                },
                                {
                                    icon: "",
                                    title: "Insight",
                                    val: launcher.profileData && launcher.profileData.insight !== undefined ? launcher.profileData.insight.toString() : "0",
                                    col: "#f5c342"
                                },
                                {
                                    icon: "",
                                    title: "Deaths",
                                    val: launcher.profileData && launcher.profileData.deaths !== undefined ? launcher.profileData.deaths.toString() : "0",
                                    col: "#e86b6b"
                                },
                                {
                                    icon: "",
                                    title: "Trophies",
                                    val: (launcher.profileData && launcher.profileData.trophies_earned !== undefined ? launcher.profileData.trophies_earned : 0) + " / " + (launcher.profileData && launcher.profileData.trophies_total !== undefined ? launcher.profileData.trophies_total : 40),
                                    col: "#f5c342"
                                }
                            ]
                            delegate: Rectangle {
                                width: 112
                                height: 60
                                radius: 6
                                color: "#0a0d13"
                                border.width: 1
                                border.color: "#1c2330"

                                Column {
                                    anchors.centerIn: parent
                                    spacing: 3

                                    Row {
                                        spacing: 4
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        Text { text: modelData.icon; font.pixelSize: 10 }
                                        Text {
                                            text: modelData.title
                                            color: Theme.textFaint
                                            font.family: Theme.sans
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                        }
                                    }

                                    Text {
                                        text: modelData.val
                                        color: modelData.col
                                        font.family: Theme.serif
                                        font.pixelSize: 15
                                        font.weight: Font.Bold
                                        anchors.horizontalCenter: parent.horizontalCenter
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Fallback when no save data
            Rectangle {
                visible: !launcher.profileData || !launcher.profileData.valid
                width: parent.width
                height: 80
                radius: 8
                color: "#10141c"
                border.width: 1
                border.color: "#222a38"

                Column {
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        text: "No Bloodborne save data detected"
                        color: Theme.text
                        font.family: Theme.serif
                        font.pixelSize: 15
                        font.weight: Font.Bold
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                        text: "Set your User / Saves directory in Settings → Game & Saves, or launch Bloodborne to create a character"
                        color: Theme.textDim
                        font.family: Theme.sans
                        font.pixelSize: 11
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }

            // Divider
            Rectangle { width: parent.width; height: 1; color: "#1c2330" }

            // ==========================================================
            // DUAL-COLUMN TROPHY SHOWCASE
            // ==========================================================
            Item {
                width: parent.width
                height: card.height - 188

                Row {
                    anchors.fill: parent
                    spacing: 14

                    // ======================================================
                    // LEFT COLUMN: EARNED TROPHIES + PROGRESSION
                    // ======================================================
                    Rectangle {
                        width: (parent.width - 14) * 0.44
                        height: parent.height
                        color: "#080a0f"
                        radius: 8
                        border.width: 1
                        border.color: "#1c2330"

                        Column {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 10

                            // Column Header
                            Row {
                                width: parent.width
                                spacing: 8

                                Text {
                                    text: "EARNED TROPHIES"
                                    color: "#f0ede7"
                                    font.family: Theme.serif
                                    font.pixelSize: 13
                                    font.weight: Font.Bold
                                    font.letterSpacing: 1.2
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Rectangle {
                                    height: 18
                                    width: earnedPillText.implicitWidth + 12
                                    radius: 9
                                    color: "#163321"
                                    border.width: 1
                                    border.color: Theme.good
                                    anchors.verticalCenter: parent.verticalCenter

                                    Text {
                                        id: earnedPillText
                                        anchors.centerIn: parent
                                        text: (launcher.profileData && launcher.profileData.earned_trophies ? launcher.profileData.earned_trophies.length : 0) + " Unlocked"
                                        color: Theme.good
                                        font.family: Theme.sans
                                        font.pixelSize: 10
                                        font.weight: Font.Bold
                                    }
                                }
                            }

                            // Hunt Progression & Completion Box
                            Rectangle {
                                width: parent.width
                                height: 86
                                radius: 6
                                color: "#0e1219"
                                border.width: 1
                                border.color: "#1f2735"

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 6

                                    Row {
                                        width: parent.width

                                        Text {
                                            text: "HUNT PROGRESSION"
                                            color: Theme.textFaint
                                            font.family: Theme.sans
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            font.letterSpacing: 1.0
                                        }

                                        Item { width: 1; height: 1 }

                                        Text {
                                            anchors.right: parent.right
                                            text: (launcher.profileData && launcher.profileData.completion_pct !== undefined ? launcher.profileData.completion_pct : 0) + "% COMPLETED"
                                            color: "#f5c342"
                                            font.family: Theme.serif
                                            font.pixelSize: 11
                                            font.weight: Font.Bold
                                        }
                                    }

                                    // Progress Bar
                                    Rectangle {
                                        width: parent.width
                                        height: 8
                                        radius: 4
                                        color: "#07090d"
                                        border.width: 1
                                        border.color: "#1a212c"

                                        Rectangle {
                                            height: parent.height
                                            radius: 4
                                            width: parent.width * Math.min(1.0, (launcher.profileData && launcher.profileData.completion_pct ? launcher.profileData.completion_pct / 100 : 0))
                                            gradient: Gradient {
                                                orientation: Gradient.Horizontal
                                                GradientStop { position: 0.0; color: Theme.accent }
                                                GradientStop { position: 1.0; color: "#f5c342" }
                                            }
                                        }
                                    }

                                    // Grade Breakdown Chips
                                    Row {
                                        width: parent.width
                                        spacing: 6
                                        anchors.horizontalCenter: parent.horizontalCenter

                                        Repeater {
                                            model: [
                                                {grade: "P", label: "Platinum", val: launcher.profileData ? launcher.profileData.platinum_str : "0/1", col: "#5dd3f3", bg: "#162e38"},
                                                {grade: "G", label: "Gold", val: launcher.profileData ? launcher.profileData.gold_str : "0/6", col: "#f5c342", bg: "#2e2410"},
                                                {grade: "S", label: "Silver", val: launcher.profileData ? launcher.profileData.silver_str : "0/9", col: "#d4dbe2", bg: "#22272e"},
                                                {grade: "B", label: "Bronze", val: launcher.profileData ? launcher.profileData.bronze_str : "3/24", col: "#cd7f32", bg: "#2b1c14"}
                                            ]
                                            delegate: Rectangle {
                                                width: (parent.width - 18) / 4
                                                height: 24
                                                radius: 4
                                                color: modelData.bg
                                                border.width: 1
                                                border.color: modelData.col

                                                Row {
                                                    anchors.centerIn: parent
                                                    spacing: 4
                                                    Text { text: modelData.label.charAt(0); color: modelData.col; font.family: Theme.serif; font.pixelSize: 10; font.weight: Font.Bold }
                                                    Text { text: modelData.val; color: "#f0ede7"; font.family: Theme.sans; font.pixelSize: 10; font.weight: Font.Bold }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // Earned Trophies List
                            ListView {
                                id: earnedListView
                                width: parent.width
                                height: parent.height - 128
                                clip: true
                                boundsBehavior: Flickable.StopAtBounds
                                spacing: 8
                                model: launcher.profileData ? launcher.profileData.earned_trophies : []
                                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                                delegate: Rectangle {
                                    id: earnedDelegate
                                    width: earnedListView.width - 6
                                    height: 68
                                    radius: 6
                                    color: earnedMouse.containsMouse ? "#18202c" : "#10151f"
                                    border.width: 1
                                    border.color: earnedMouse.containsMouse ? "#d4af37" : "#6e5728"

                                    MouseArea {
                                        id: earnedMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                    }

                                    Row {
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        spacing: 10

                                        // Ornate Gold Trophy Icon Frame
                                        Rectangle {
                                            width: 52
                                            height: 52
                                            radius: 4
                                            color: "#080a0e"
                                            border.width: 1
                                            border.color: "#856a31"
                                            anchors.verticalCenter: parent.verticalCenter

                                            Image {
                                                anchors.fill: parent
                                                anchors.margins: 2
                                                source: Qt.resolvedUrl("../assets/trophies/" + modelData.icon)
                                                fillMode: Image.PreserveAspectFit
                                                smooth: true
                                            }
                                        }

                                        Column {
                                            width: parent.width - 68
                                            spacing: 3
                                            anchors.verticalCenter: parent.verticalCenter

                                            Row {
                                                width: parent.width
                                                spacing: 6

                                                Text {
                                                    text: modelData.name
                                                    color: "#f0ede7"
                                                    font.family: Theme.serif
                                                    font.pixelSize: 13
                                                    font.weight: Font.Bold
                                                    elide: Text.ElideRight
                                                    width: Math.min(implicitWidth, parent.width - 80)
                                                }

                                                Rectangle {
                                                    height: 16
                                                    width: gradeEarnedTxt.implicitWidth + 8
                                                    radius: 3
                                                    color: modal.gradeBg(modelData.grade)
                                                    border.width: 1
                                                    border.color: modal.gradeColor(modelData.grade)
                                                    anchors.verticalCenter: parent.verticalCenter

                                                    Text {
                                                        id: gradeEarnedTxt
                                                        anchors.centerIn: parent
                                                        text: modelData.grade_name
                                                        color: modal.gradeColor(modelData.grade)
                                                        font.family: Theme.sans
                                                        font.pixelSize: 9
                                                        font.weight: Font.Bold
                                                    }
                                                }
                                            }

                                            Text {
                                                text: modelData.description
                                                color: Theme.textDim
                                                font.family: Theme.sans
                                                font.pixelSize: 10
                                                wrapMode: Text.WordWrap
                                                width: parent.width
                                                maximumLineCount: 2
                                                elide: Text.ElideRight
                                            }

                                            Text {
                                                text: "✓ " + (modelData.unlocked_at ? modelData.unlocked_at : "Unlocked")
                                                color: Theme.good
                                                font.family: Theme.sans
                                                font.pixelSize: 9
                                                font.weight: Font.Bold
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // ======================================================
                    // RIGHT COLUMN: LOCKED TROPHIES & SEARCH / FILTERS
                    // ======================================================
                    Rectangle {
                        width: (parent.width - 14) * 0.56
                        height: parent.height
                        color: "#080a0f"
                        radius: 8
                        border.width: 1
                        border.color: "#1c2330"

                        Column {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 8

                            // Header + Search Row
                            Row {
                                width: parent.width
                                height: 30
                                spacing: 8

                                Row {
                                    spacing: 8
                                    anchors.verticalCenter: parent.verticalCenter

                                    Text {
                                        text: "LOCKED TROPHIES"
                                        color: "#f0ede7"
                                        font.family: Theme.serif
                                        font.pixelSize: 13
                                        font.weight: Font.Bold
                                        font.letterSpacing: 1.2
                                        anchors.verticalCenter: parent.verticalCenter
                                    }

                                    Rectangle {
                                        height: 18
                                        width: lockedPillText.implicitWidth + 12
                                        radius: 9
                                        color: "#212836"
                                        border.width: 1
                                        border.color: "#3d4b63"
                                        anchors.verticalCenter: parent.verticalCenter

                                        Text {
                                            id: lockedPillText
                                            anchors.centerIn: parent
                                            text: (launcher.profileData && launcher.profileData.locked_trophies ? launcher.profileData.locked_trophies.length : 37) + " Remaining"
                                            color: Theme.textDim
                                            font.family: Theme.sans
                                            font.pixelSize: 10
                                            font.weight: Font.Bold
                                        }
                                    }
                                }

                                Item { width: 1; height: 1 }

                                // Search Box
                                Rectangle {
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 190
                                    height: 28
                                    radius: 6
                                    color: "#0d1117"
                                    border.width: 1
                                    border.color: searchInput.activeFocus ? Theme.accent : "#242d3c"

                                    Row {
                                        anchors.fill: parent
                                        anchors.leftMargin: 8
                                        anchors.rightMargin: 6
                                        spacing: 6

                                        Text {
                                            text: ""
                                            font.pixelSize: 10
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        TextInput {
                                            id: searchInput
                                            width: parent.width - 38
                                            anchors.verticalCenter: parent.verticalCenter
                                            color: Theme.text
                                            font.family: Theme.sans
                                            font.pixelSize: 11
                                            clip: true
                                            onTextChanged: modal.searchQuery = text

                                            Text {
                                                text: "Search trophies..."
                                                color: Theme.textFaint
                                                font.family: Theme.sans
                                                font.pixelSize: 11
                                                visible: !searchInput.text && !searchInput.activeFocus
                                            }
                                        }

                                        Text {
                                            visible: searchInput.text.length > 0
                                            text: "x"
                                            color: Theme.textDim
                                            font.pixelSize: 10
                                            anchors.verticalCenter: parent.verticalCenter

                                            MouseArea {
                                                anchors.fill: parent
                                                onClicked: {
                                                    searchInput.text = ""
                                                    modal.searchQuery = ""
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // Category Filter Chips
                            Row {
                                spacing: 6
                                width: parent.width

                                Repeater {
                                    model: [
                                        {key: "All", label: "All (" + (launcher.profileData && launcher.profileData.locked_total_count !== undefined ? launcher.profileData.locked_total_count : "37") + ")"},
                                        {key: "Boss", label: "Bosses (" + (launcher.profileData && launcher.profileData.locked_boss_count !== undefined ? launcher.profileData.locked_boss_count : "16") + ")"},
                                        {key: "Story", label: "Story (" + (launcher.profileData && launcher.profileData.locked_story_count !== undefined ? launcher.profileData.locked_story_count : "7") + ")"},
                                        {key: "Equipment", label: "Gear (" + (launcher.profileData && launcher.profileData.locked_equip_count !== undefined ? launcher.profileData.locked_equip_count : "9") + ")"},
                                        {key: "Chalice", label: "Chalice (" + (launcher.profileData && launcher.profileData.locked_chalice_count !== undefined ? launcher.profileData.locked_chalice_count : "5") + ")"}
                                    ]
                                    delegate: Rectangle {
                                        height: 22
                                        width: chipText.implicitWidth + 14
                                        radius: 4
                                        color: modal.lockedCategory === modelData.key ? "#301318" : "#0d1117"
                                        border.width: 1
                                        border.color: modal.lockedCategory === modelData.key ? Theme.accent : "#222a38"

                                        Text {
                                            id: chipText
                                            anchors.centerIn: parent
                                            text: modelData.label
                                            color: modal.lockedCategory === modelData.key ? "#ff6b75" : Theme.textDim
                                            font.family: Theme.sans
                                            font.pixelSize: 10
                                            font.weight: modal.lockedCategory === modelData.key ? Font.Bold : Font.Normal
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: modal.lockedCategory = modelData.key
                                        }
                                    }
                                }
                            }

                            Rectangle { width: parent.width; height: 1; color: "#1c2330" }

                            // Locked Trophies List
                            ListView {
                                id: lockedListView
                                width: parent.width
                                height: parent.height - 76
                                clip: true
                                boundsBehavior: Flickable.StopAtBounds
                                spacing: 8
                                model: modal.filterTrophies(launcher.profileData ? launcher.profileData.locked_trophies : [], modal.lockedCategory, modal.searchQuery)
                                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                                delegate: Rectangle {
                                    id: lockedDelegate
                                    width: lockedListView.width - 6
                                    height: 66
                                    radius: 6
                                    color: lockedMouse.containsMouse ? "#141924" : "#0b0f16"
                                    border.width: 1
                                    border.color: lockedMouse.containsMouse ? "#3b485d" : "#1a212e"

                                    MouseArea {
                                        id: lockedMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                    }

                                    Row {
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        spacing: 10

                                        // Silhouette Trophy Icon with Padlock
                                        Rectangle {
                                            width: 50
                                            height: 50
                                            radius: 4
                                            color: "#07090d"
                                            border.width: 1
                                            border.color: "#1d2431"
                                            anchors.verticalCenter: parent.verticalCenter

                                            Image {
                                                anchors.fill: parent
                                                anchors.margins: 2
                                                source: Qt.resolvedUrl("../assets/trophies/" + modelData.icon)
                                                fillMode: Image.PreserveAspectFit
                                                smooth: true
                                                opacity: 0.28
                                            }

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: 4
                                                color: "#40000000"
                                            }

                                            Text {
                                                anchors.centerIn: parent
                                                text: "🔒"
                                                font.pixelSize: 15
                                                opacity: 0.85
                                            }
                                        }

                                        Column {
                                            width: parent.width - 66
                                            spacing: 3
                                            anchors.verticalCenter: parent.verticalCenter

                                            Row {
                                                width: parent.width
                                                spacing: 6

                                                Text {
                                                    text: modelData.name
                                                    color: "#e0ded9"
                                                    font.family: Theme.serif
                                                    font.pixelSize: 13
                                                    font.weight: Font.Bold
                                                    elide: Text.ElideRight
                                                    width: Math.min(implicitWidth, parent.width - 80)
                                                }

                                                Rectangle {
                                                    height: 16
                                                    width: gradeLockedTxt.implicitWidth + 8
                                                    radius: 3
                                                    color: "#181d24"
                                                    border.width: 1
                                                    border.color: "#2e3644"
                                                    anchors.verticalCenter: parent.verticalCenter

                                                    Text {
                                                        id: gradeLockedTxt
                                                        anchors.centerIn: parent
                                                        text: modelData.grade_name
                                                        color: modal.gradeColor(modelData.grade)
                                                        font.family: Theme.sans
                                                        font.pixelSize: 9
                                                        font.weight: Font.Bold
                                                    }
                                                }
                                            }

                                            Text {
                                                text: modelData.description
                                                color: Theme.textDim
                                                font.family: Theme.sans
                                                font.pixelSize: 10
                                                wrapMode: Text.WordWrap
                                                width: parent.width
                                                maximumLineCount: 2
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
