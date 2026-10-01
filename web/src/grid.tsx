import type { ReactNode } from "react";

type Layout = "sign-in" | "chat";

// Placed in cells from the center, where a line runs, so the cleared block and the lit cells sit on the lines. The
// block holds the content; the lit cells keep to the outer columns, or to the top rows of a phone's sign-in, so
// none sits behind text or glass (the identity guide's Motifs). A phone's empty chat fills its screen, so it has none.
const BLOCK: Record<Layout, string> = {
  "sign-in":
    "left-[calc(50%-7*var(--cell)+1px)] top-[calc(50%-7*var(--cell)+1px)] h-[calc(14*var(--cell)-1px)] w-[calc(14*var(--cell)-1px)] sm:left-[calc(50%-5*var(--cell)+1px)] sm:top-[calc(50%-5*var(--cell)+1px)] sm:h-[calc(10*var(--cell)-1px)] sm:w-[calc(10*var(--cell)-1px)]",
  chat: "left-[calc(50%-7*var(--cell)+1px)] top-[calc(50%-8*var(--cell)+1px)] h-[calc(16*var(--cell)-1px)] w-[calc(14*var(--cell)-1px)] sm:left-[calc(50%-8*var(--cell)+1px)] sm:top-[calc(50%-5*var(--cell)+1px)] sm:h-[calc(10*var(--cell)-1px)] sm:w-[calc(16*var(--cell)-1px)]",
};

const ON_PHONES = [
  "sm:hidden left-[calc(50%-4*var(--cell)+1px)] top-[calc(50%-8*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
  "sm:hidden left-[calc(50%-3*var(--cell)+1px)] top-[calc(50%-9*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
  "sm:hidden left-[calc(50%+1*var(--cell)+1px)] top-[calc(50%-9*var(--cell)+1px)] h-[calc(var(--cell)-1px)] w-[calc(2*var(--cell)-1px)]",
  "sm:hidden left-[calc(50%+3*var(--cell)+1px)] top-[calc(50%-8*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
];

const LIT: Record<Layout, string[]> = {
  "sign-in": [
    ...ON_PHONES,
    "max-sm:hidden left-[calc(50%-9*var(--cell)+1px)] top-[calc(50%-3*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%-10*var(--cell)+1px)] top-[calc(50%-2*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%-8*var(--cell)+1px)] top-[calc(50%+1px)] h-[calc(var(--cell)-1px)] w-[calc(2*var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%+6*var(--cell)+1px)] top-[calc(50%-2*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%+8*var(--cell)+1px)] top-[calc(50%-1*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%+9*var(--cell)+1px)] top-[calc(50%+1px)] size-[calc(var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%+7*var(--cell)+1px)] top-[calc(50%+1*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
  ],
  chat: [
    "max-sm:hidden left-[calc(50%-9*var(--cell)+1px)] top-[calc(50%-3*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%-10*var(--cell)+1px)] top-[calc(50%-2*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%-10*var(--cell)+1px)] top-[calc(50%+1*var(--cell)+1px)] h-[calc(var(--cell)-1px)] w-[calc(2*var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%+8*var(--cell)+1px)] top-[calc(50%-3*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%+9*var(--cell)+1px)] top-[calc(50%-2*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%+9*var(--cell)+1px)] top-[calc(50%+1px)] size-[calc(var(--cell)-1px)]",
    "max-sm:hidden left-[calc(50%+8*var(--cell)+1px)] top-[calc(50%+2*var(--cell)+1px)] size-[calc(var(--cell)-1px)]",
  ],
};

// The banner's grid behind a page's content: hairlines that fade toward the edges, a block cleared for the content,
// and a few lit cells. Static once it has arrived: the lines fade in, the content rises, and the cells come on last
// (the identity guide's Motifs). The hairlines run on under the shell's rail and bar (by --rail and --bar), centered
// on the content all the same; the block and the lit cells keep to the page. The cells are whole pixels, and the lines
// are drawn from a corner whole cells off the center, as the block is placed, so a browser rounds the two alike and
// the lines meet the block on every side.
export function Grid({
  layout,
  children,
}: {
  layout: Layout;
  children: ReactNode;
}) {
  return (
    <div className="relative isolate flex flex-1 flex-col">
      <div
        aria-hidden="true"
        data-grid={layout}
        className="pointer-events-none absolute inset-0 -z-10"
      >
        <div className="absolute -top-(--bar) right-0 bottom-0 -left-(--rail) animate-fade overflow-hidden">
          <div className="absolute top-0 -right-(--rail) -bottom-(--bar) left-0 [mask-image:radial-gradient(ellipse_at_center,black_45%,transparent_85%)]">
            <div className="absolute top-[calc(50%-64*var(--cell))] left-[calc(50%-64*var(--cell))] size-[calc(128*var(--cell))] bg-[linear-gradient(to_right,rgb(255_255_255/0.1)_1px,transparent_1px),linear-gradient(to_bottom,rgb(255_255_255/0.1)_1px,transparent_1px)] bg-size-[var(--cell)_var(--cell)]" />
          </div>
        </div>
        <div className="absolute inset-0 overflow-hidden">
          <div className={`absolute bg-night ${BLOCK[layout]}`} />
          {LIT[layout].map((place) => (
            <div
              key={place}
              className={`absolute animate-light lit ${place}`}
            />
          ))}
        </div>
      </div>
      <div className="flex flex-1 animate-arrive flex-col motion-reduce:animate-fade">
        {children}
      </div>
    </div>
  );
}
