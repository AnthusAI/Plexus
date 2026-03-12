// Mock for remark-breaks plugin
module.exports = {
  default: function remarkBreaks() {
    return function transformer() {
      // No-op transformer
    };
  }
}; 