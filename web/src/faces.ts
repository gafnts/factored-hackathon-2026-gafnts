const FACES = [
  '600 1em "Outfit Variable"',
  '1em "Geist Variable"',
  '1em "Geist Mono Variable"',
];

// Asked for at once, rather than when a line first needs one, so a page can wait for its faces and arrive whole, with
// no line reflowing as a face comes in; a second at most, after which the fallbacks stand.
export function faces(): Promise<void> {
  let timer = 0;
  const late = new Promise<void>((resolve) => {
    timer = window.setTimeout(resolve, 1000);
  });
  const loaded = Promise.all(FACES.map((face) => document.fonts.load(face)));
  return Promise.race([
    loaded.then(
      () => undefined,
      () => undefined,
    ),
    late,
  ]).finally(() => {
    window.clearTimeout(timer);
  });
}
