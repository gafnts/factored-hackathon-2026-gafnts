import type { Language } from "../contracts/chat";
import { Page } from "../layout";
import { TEXTS } from "../texts";

export function NotFound({ language }: { language: Language }) {
  const texts = TEXTS[language];
  return (
    <Page language={language}>
      <section className="py-10">
        <h1 className="text-2xl font-bold tracking-tight">{texts.notFound}</h1>
        <a className="mt-6 inline-block text-ember underline" href="/chat">
          {texts.toChat}
        </a>
      </section>
    </Page>
  );
}
