// Mock for remark-gfm plugin
module.exports = {
  default: function remarkGfm() {
    return function transformer() {
      // No-op transformer
    };
  }
}; 