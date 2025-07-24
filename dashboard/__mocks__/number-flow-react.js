// CommonJS Mock for @number-flow/react component
function NumberFlowMock({ value, format, ...props }) {
  if (typeof value !== 'number') return value.toString();
  
  // Apply formatting if provided
  let formattedValue;
  if (format) {
    const options = {
      minimumFractionDigits: format.minimumFractionDigits || 0,
      maximumFractionDigits: format.maximumFractionDigits || 0,
      useGrouping: format.useGrouping !== false
    };
    formattedValue = value.toLocaleString('en-US', options);
  } else {
    formattedValue = value.toString();
  }
  
  return formattedValue;
}

module.exports = NumberFlowMock;
module.exports.default = NumberFlowMock; 