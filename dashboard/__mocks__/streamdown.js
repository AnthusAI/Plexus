const React = require("react");

function Streamdown({ children, className }) {
  return React.createElement("div", { className }, children);
}

module.exports = {
  Streamdown,
};
