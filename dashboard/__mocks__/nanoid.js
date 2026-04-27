let counter = 0;

function nanoid() {
  counter += 1;
  return `mock-nanoid-${counter}`;
}

module.exports = {
  nanoid,
};
