import QtQuick
import Quickshell
import Quickshell.Io

// Omarchy bar widget for omarchy-handsfree. It reads the daemon's state file
// and shows a glyph only while the microphone or camera can be in use, so an
// empty slot means both are closed. Left click: listen. Right click: eyes.
Item {
  id: root

  property var bar
  property string moduleName
  property var settings

  property var status: ({})
  readonly property bool listening: status.listening === true
  readonly property bool voice: status.voice === "continuous"
  readonly property bool gaze: status.gaze === true
  readonly property bool dictation: status.dictation === true
  readonly property bool grid: status.grid === true

  readonly property string label: {
    const parts = []
    if (listening || voice) parts.push(String.fromCodePoint(0xF036C))
    if (dictation) parts.push(String.fromCodePoint(0xF03EB))
    if (gaze) parts.push(String.fromCodePoint(0xF0208))
    if (grid) parts.push(String.fromCodePoint(0xF0570))
    return parts.join(" ")
  }

  readonly property string tooltip: {
    const lines = []
    lines.push(listening ? "Listening now" : (voice ? "Listening continuously" : "Microphone closed (push-to-talk)"))
    if (dictation) lines.push("Dictation on")
    lines.push(gaze ? "Eye tracking on (camera open)" : "Camera closed")
    return lines.join("\n")
  }

  visible: label !== ""
  implicitWidth: visible ? glyphs.implicitWidth + 12 : 0
  implicitHeight: bar ? bar.barSize : 26

  function parse(raw) {
    try {
      const parsed = JSON.parse(raw)
      root.status = parsed && typeof parsed === "object" ? parsed : ({})
    } catch (error) {
      root.status = ({})
    }
  }

  FileView {
    id: stateFile
    path: Quickshell.env("XDG_RUNTIME_DIR") + "/handsfree/state.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.parse(text())
    onLoadFailed: root.status = ({})
  }

  // The daemon replaces the file atomically, which can drop a file watch;
  // a cheap poll keeps the indicator honest.
  Timer {
    interval: 1500
    running: true
    repeat: true
    onTriggered: stateFile.reload()
  }

  Text {
    id: glyphs
    anchors.centerIn: parent
    textFormat: Text.PlainText
    text: root.label
    color: root.bar ? (root.listening ? root.bar.urgent : root.bar.foreground) : "white"
    font.family: root.bar ? root.bar.fontFamily : "monospace"
    font.pixelSize: 13
  }

  MouseArea {
    anchors.fill: parent
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    hoverEnabled: true
    onClicked: function(mouse) {
      if (!root.bar) return
      root.bar.run(mouse.button === Qt.RightButton ? "@BIN@/handsfree-ctl gaze toggle" : "@BIN@/handsfree-ctl listen")
    }
    onEntered: if (root.bar) root.bar.showTooltip(root, root.tooltip)
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }
}
