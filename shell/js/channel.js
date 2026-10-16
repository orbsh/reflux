// Reflux shell — the channel: one WebSocket per session, ops down, events up.
//
// The shell speaks first. On open it sends `reflux:hello` with the two things only the client
// knows — the path it is standing on, and the previous session's token when there is one — and
// the producer answers with structure. Anything the shell cannot send is counted, never
// silently dropped: silent degradation is not an option in this design.
//
// Frames are JSON text, one frame per message: `{ev, ops}` down, `{event, id, data}` up.

export function openChannel({ onFrame, onNote = () => {} }) {
  const url = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`;
  const counters = { sent: 0, unsent: 0, received: 0 };
  let socket = null;

  function send(frame) {
    if (!socket || socket.readyState !== 1) {
      counters.unsent++;
      onNote(`no channel for ${frame.event}`);
      return false;
    }
    socket.send(JSON.stringify(frame));
    counters.sent++;
    return true;
  }

  const socketFor = new WebSocket(url);
  socket = socketFor;
  socket.onopen = () => {
    send({ event: "reflux:hello", data: { path: location.pathname, token: null } });
  };
  socket.onmessage = (message) => {
    let frame;
    try {
      frame = JSON.parse(message.data);
    } catch {
      onNote(`not JSON: ${message.data}`);
      return;
    }
    counters.received++;
    onFrame(frame);
  };
  socket.onclose = () => onNote("channel closed");
  socket.onerror = () => onNote("channel error");

  return { send, counters, close: () => socket.close(), url };
}