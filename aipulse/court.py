"""AI in court (ai-in-court/): lawsuits against AI makers over copyright, privacy and people's likeness since 2023, in
every country the news we read covers: who sued whom, where, and where each case stands. Every case is checked by hand
against the stories that reported it and listed in CASES with its steps (filed, an early ruling, a decision, a
settlement, thrown out), each step tied to the story that reported it. A case stands where its latest step leaves it,
so the page follows the steps as rulings come in. `python -m aipulse court` lists the lawsuit stories not checked yet,
to add as a new case, a new step, or to LEFT_OUT. Linked from Industry's strip on the front page.
"""
from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

from . import pages, rss

PATH = "ai-in-court/"
SINCE = "2023-01-01"

# what a lawsuit is about: (its words on the page, what it means)
KINDS = {
    "copyright": ("Copyright", "Over books, articles, songs, pictures and films used to train AI or copied by it."),
    "privacy": ("Privacy", "Over personal data taken, shared or recorded by AI products."),
    "likeness": ("Likeness", "Over a person's face, voice or name copied by AI without consent."),
}

# where a case stands after a step: (its words on the page, its colour: Okabe-Ito, dark text on it, open?)
STATUSES = {
    "filed": ("Filed", "#56B4E9", True),
    "early": ("Early ruling", "#E69F00", True),
    "part": ("Partly settled", "#F0E442", True),
    "won": ("Those suing won", "#CC79A7", False),
    "lost": ("Those sued won", "#009E73", False),
    "settled": ("Settled", "#D55E00", False),
    "out": ("Thrown out", "#9AA0AA", False),
}

# Every case the page shows, checked by hand: who sued, whom, the country of the court, the month it was filed, what
# it's about, and its steps, each the URL of the story that reported it, where the case stood after it, and what
# happened, in short. Checked 13 Oct 2026.
CASES: list[dict] = [
    # copyright: news
    dict(kind="copyright", by="The New York Times", sued="OpenAI and Microsoft", where="US", filed="2023-12",
         about="Millions of articles used to train ChatGPT",
         steps=[("https://the-decoder.com/new-york-times-files-lawsuit-against-openai-and-microsoft-demanding-destruction-of-chatgpt/",
                 "filed", "Sued, asking for damages and for models trained on its articles to be destroyed"),
                ("https://siliconangle.com/2025/03/26/new-york-judge-allows-new-york-times-copyright-lawsuit-openai-proceed/",
                 "early", "A judge turned down OpenAI's request to throw the case out")]),
    dict(kind="copyright", by="Eight US newspapers, including the New York Daily News", sued="OpenAI and Microsoft",
         where="US", filed="2024-04", about="News articles used to train AI",
         steps=[("https://the-decoder.com/eight-more-publishers-sue-openai-and-microsoft-for-massive-copyright-infringement/",
                 "filed", "Sued in a New York federal court")]),
    dict(kind="copyright", by="The Intercept", sued="OpenAI", where="US", filed="",
         about="Articles used in training with their author and copyright details removed",
         steps=[("https://the-decoder.com/judge-allows-the-intercepts-main-dmca-complaint-against-openai-to-proceed/",
                 "early", "A judge let its main claim go ahead")]),
    dict(kind="copyright", by="Raw Story and AlterNet", sued="OpenAI", where="US", filed="",
         about="Articles used in training with their author and copyright details removed",
         steps=[("https://the-decoder.com/openai-scores-key-legal-victory-as-judge-throws-out-copyright-case-brought-by-news-websites/",
                 "out", "A New York federal judge threw the case out")]),
    dict(kind="copyright", by="Dow Jones and the New York Post (News Corp)", sued="Perplexity", where="US",
         filed="2024-10", about="News stories copied into Perplexity's answers",
         steps=[("https://techcrunch.com/2024/10/21/content-kleptocracy-news-corp-outlets-sue-perplexity-over-scraped-stories/",
                 "filed", "Sued in New York")]),
    dict(kind="copyright", by="ANI, an Indian news agency", sued="OpenAI", where="India", filed="2024-11",
         about="News stories used to train ChatGPT",
         steps=[("https://techcrunch.com/2024/11/18/indian-news-agency-sues-openai-alleging-copyright-infringement/",
                 "filed", "Sued in the Delhi High Court"),
                ("https://the-decoder.com/delhi-high-court-hands-openai-a-win-by-rejecting-major-indian-news-agencys-copyright-injunction/",
                 "early", "The court refused ANI's request for an order stopping OpenAI while the case goes on")]),
    dict(kind="copyright", by="Canadian news companies", sued="OpenAI", where="Canada", filed="2024-11",
         about="News stories used to train ChatGPT",
         steps=[("https://techcrunch.com/2024/11/29/canadian-news-companies-sue-openai/", "filed", "Sued")]),
    dict(kind="copyright", by="14 publishers, including Condé Nast, The Atlantic and Forbes", sued="Cohere", where="US",
         filed="2025-02", about="Articles used to train and answer with AI",
         steps=[("https://techcrunch.com/2025/02/13/publishers-sue-ai-startup-cohere-over-alleged-copyright-infringement/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Reddit", sued="Perplexity and three data-scraping firms", where="US", filed="2025-10",
         about="Reddit posts scraped to train AI",
         steps=[("https://siliconangle.com/2025/10/22/reddit-suing-perplexity-ai-data-scraping-firms-using-data-without-permission/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Chicago Tribune", sued="Perplexity", where="US", filed="2025-12",
         about="Journalism copied into Perplexity's answers",
         steps=[("https://incidentdatabase.ai/cite/1298", "filed", "Sued in a federal court")]),
    dict(kind="copyright", by="The New York Times", sued="Perplexity", where="US", filed="2025-12",
         about="Articles used to train AI and copied into its answers",
         steps=[("https://techcrunch.com/2025/12/05/the-new-york-times-is-suing-perplexity-for-copyright-infringement/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Encyclopedia Britannica and Merriam-Webster", sued="OpenAI", where="US", filed="2026-03",
         about="Almost 100,000 articles used to train AI",
         steps=[("https://techcrunch.com/2026/03/16/merriam-webster-openai-encyclopedia-brittanica-lawsuit/", "filed",
                 "Sued")]),
    dict(kind="copyright", by="The Seattle Times and Newsday", sued="OpenAI and Microsoft", where="US", filed="2026-09",
         about="Journalism used to train AI",
         steps=[("https://techcrunch.com/2026/09/05/seattle-times-and-newsday-are-the-latest-publications-to-sue-openai-and-microsoft/",
                 "filed", "Sued")]),
    # copyright: books
    dict(kind="copyright", by="Sarah Silverman and other authors", sued="Meta", where="US", filed="2023-07",
         about="Books used to train Llama",
         steps=[("https://siliconangle.com/2023/07/10/comedian-sarah-silverman-sues-openai-meta-copyright-infringement/",
                 "filed", "Sued"),
                ("https://techcrunch.com/2025/03/08/judge-allows-authors-ai-copyright-lawsuit-against-meta-to-move-forward/",
                 "early", "A judge let the case go ahead, but dismissed part of it"),
                ("https://techcrunch.com/2025/06/25/federal-judge-sides-with-meta-in-lawsuit-over-training-ai-models-on-copyrighted-books/",
                 "lost", "A federal judge sided with Meta")]),
    dict(kind="copyright", by="Sarah Silverman and other authors", sued="OpenAI", where="US", filed="2023-07",
         about="Books used to train ChatGPT",
         steps=[("https://siliconangle.com/2023/07/10/comedian-sarah-silverman-sues-openai-meta-copyright-infringement/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Authors led by Michael Chabon", sued="Meta and OpenAI", where="US", filed="2023-09",
         about="Books used to train AI",
         steps=[("https://the-decoder.com/generative-ai-needs-a-court-ruling-on-fair-use-of-training-data/", "filed",
                 "Sued in a San Francisco federal court")]),
    dict(kind="copyright", by="George R.R. Martin and other authors", sued="OpenAI", where="US", filed="2023-09",
         about="Books used to train ChatGPT",
         steps=[("https://the-decoder.com/game-of-thrones-author-george-r-r-martin-and-other-bestselling-authors-sue-openai/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Authors, including Mike Huckabee", sued="Bloomberg, Microsoft and Meta", where="US",
         filed="2023-10", about="Pirated books used to train AI",
         steps=[("https://the-decoder.com/new-lawsuit-accuses-bloomberg-microsoft-and-meta-of-training-ai-with-pirated-books/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Nonfiction authors, including Julian Sancton", sued="OpenAI and Microsoft", where="US",
         filed="2023-11", about="Nonfiction books used to train AI",
         steps=[("https://siliconangle.com/2023/11/22/microsoft-openai-sued-alleged-unauthorized-use-nonfiction-authors-work-ai-training/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Authors Nicholas Basbanes and Nicholas Gage", sued="OpenAI and Microsoft", where="US",
         filed="2024-01", about="Books used to train AI",
         steps=[("https://the-decoder.com/microsoft-and-openai-hit-with-another-copyright-lawsuit-over-ai-training-using-authors-books/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Authors", sued="Nvidia", where="US", filed="2024-03", about="Books used to train AI",
         steps=[("https://the-decoder.com/authors-sue-ai-chip-giant-nvidia-for-copyright-infringement/", "filed",
                 "Sued")]),
    dict(kind="copyright", by="Authors (Bartz and others)", sued="Anthropic", where="US", filed="2024-08",
         about="Books used to train Claude, many downloaded from pirate sites",
         steps=[("https://the-decoder.com/authors-sue-anthropic-in-class-action-over-alleged-copyright-infringement/",
                 "filed", "Sued as a class action"),
                ("https://techcrunch.com/2025/06/24/a-federal-judge-sides-with-anthropic-in-lawsuit-over-training-ai-on-books-without-authors-permission/",
                 "early", "A judge ruled training on bought books was lawful, but sent the pirated copies to trial"),
                ("https://techcrunch.com/2025/08/26/anthropic-settles-ai-book-training-lawsuit-with-authors/",
                 "settled", "Anthropic settled"),
                ("https://techcrunch.com/2026/07/20/anthropics-landmark-1-5b-copyright-settlement-is-approved/",
                 "settled", "The court approved the $1.5 billion settlement")]),
    dict(kind="copyright", by="Federation of Indian Publishers", sued="OpenAI", where="India", filed="2025-01",
         about="Books used to train ChatGPT",
         steps=[("https://the-decoder.com/indian-publishers-join-wave-of-copyright-lawsuits-against-openai/", "filed",
                 "Sued in the Delhi High Court")]),
    dict(kind="copyright", by="French authors and publishers", sued="Meta", where="France", filed="2025-03",
         about="Books used to train AI",
         steps=[("https://techcrunch.com/2025/03/12/meta-faces-publisher-copyright-ai-lawsuit-in-france/", "filed",
                 "Sued")]),
    dict(kind="copyright", by="Authors", sued="Microsoft", where="US", filed="2025-06",
         about="About 200,000 pirated books used to train a Megatron model",
         steps=[("https://the-decoder.com/microsoft-faces-a-lawsuit-alleging-it-used-200000-pirated-books-to-train-ai/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Authors Grady Hendrix and Jennifer Roberson", sued="Apple", where="US", filed="2025-09",
         about="Pirated books used to train Apple's AI",
         steps=[("https://the-decoder.com/apple-is-being-sued-by-us-authors-who-accuse-it-of-using-pirated-books-to-train-its-ai-models/",
                 "filed", "Sued in California")]),
    dict(kind="copyright", by="John Carreyrou and other authors", sued="Six AI companies", where="US", filed="2025-12",
         about="Books used to train AI; they turned down the Anthropic settlement",
         steps=[("https://techcrunch.com/2025/12/23/john-carreyrou-and-other-authors-bring-new-lawsuit-against-six-major-ai-companies/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Publishers, including Hachette, Cengage and Elsevier", sued="Google", where="US",
         filed="2026-07", about="Books used to train Google's AI",
         steps=[("https://techcrunch.com/2026/07/14/google-faces-another-ai-training-lawsuit-from-major-publishers/",
                 "filed", "Sued")]),
    # copyright: music
    dict(kind="copyright", by="Universal Music and other music publishers", sued="Anthropic", where="US",
         filed="2023-10", about="Song lyrics used to train Claude",
         steps=[("https://siliconangle.com/2023/10/19/universal-music-group-sues-ai-startup-anthropic-song-lyric-copyright-infringement/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Universal, Sony and Warner", sued="Suno", where="US", filed="2024-06",
         about="Recordings used to train an AI song maker",
         steps=[("https://siliconangle.com/2024/06/24/record-labels-file-lawsuits-ai-music-generators-suno-udio-alleging-widespread-copyright-infringement/",
                 "filed", "Sued"),
                ("https://techcrunch.com/2025/11/25/warner-music-signs-deal-with-ai-music-startup-suno-settles-lawsuit/",
                 "part", "Warner settled and signed a licensing deal"),
                ("https://the-decoder.com/ai-music-startup-suno-doubles-its-valuation-to-5-4-billion-while-fighting-major-record-labels-in-court/",
                 "part", "Universal and Sony are still suing")]),
    dict(kind="copyright", by="Universal, Sony and Warner", sued="Udio", where="US", filed="2024-06",
         about="Recordings used to train an AI song maker",
         steps=[("https://siliconangle.com/2024/06/24/record-labels-file-lawsuits-ai-music-generators-suno-udio-alleging-widespread-copyright-infringement/",
                 "filed", "Sued"),
                ("https://techcrunch.com/2025/11/19/warner-music-settles-copyright-lawsuit-with-udio-signs-deal-for-ai-music-platform/",
                 "part", "Warner settled and signed a deal")]),
    dict(kind="copyright", by="GEMA, Germany's music rights group", sued="OpenAI", where="Germany", filed="2024-11",
         about="Song lyrics used to train and answer with ChatGPT",
         steps=[("https://the-decoder.com/german-music-rights-group-gema-sues-openai-over-unlicensed-song-lyrics-in-chatgpt/",
                 "filed", "Sued in the Munich Regional Court"),
                ("https://techcrunch.com/2025/11/12/court-rules-that-openai-violated-german-copyright-law-ordered-it-to-pay-damages/",
                 "won", "The court ruled OpenAI broke German copyright law and must pay damages")]),
    dict(kind="copyright", by="GEMA, Germany's music rights group", sued="Suno", where="Germany", filed="2025-01",
         about="Songs used to train an AI song maker",
         steps=[("https://the-decoder.com/german-music-rights-org-gema-takes-us-ai-music-startup-suno-to-court-for-alleged-infringement/",
                 "filed", "Sued in Munich"),
                ("https://the-decoder.com/german-court-rules-ai-music-generator-suno-violated-copyrights-rejects-fair-use-defense/",
                 "won", "A Munich court ruled Suno broke copyright in training and in its songs")]),
    dict(kind="copyright", by="Concord, Universal and other music publishers", sued="Anthropic", where="US",
         filed="2026-01", about="More than 20,000 songs downloaded, damages put at over $3 billion",
         steps=[("https://techcrunch.com/2026/01/29/music-publishers-sue-anthropic-for-3b-over-flagrant-piracy-of-20000-works/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Sony Music and Warner", sued="Anthropic", where="US", filed="2026-08",
         about="Music downloaded and used to train AI",
         steps=[("https://techcrunch.com/2026/08/29/sony-music-warner-sue-anthropic-alleging-a-brazen-campaign-of-intellectual-property-theft/",
                 "filed", "Sued")]),
    # copyright: pictures, films and video
    dict(kind="copyright", by="Artists, including Sarah Andersen", sued="Stability AI, Midjourney and DeviantArt",
         where="US", filed="2023-01", about="Artworks used to train image makers",
         steps=[("https://the-decoder.com/artists-sue-stability-ai-midjourney-and-deviantart/", "filed",
                 "Sued as a class action"),
                ("https://siliconangle.com/2023/10/31/judge-dismisses-copyright-claims-artists-generative-ai-art-providers/",
                 "early", "A judge dismissed most of the claims"),
                ("https://techcrunch.com/2024/08/12/artists-lawsuit-against-generative-ai-makers-can-go-forward-judge-says/",
                 "early", "A judge let part of the case go ahead")]),
    dict(kind="copyright", by="Getty Images", sued="Stability AI", where="UK", filed="2023-01",
         about="Millions of photos used to train Stable Diffusion",
         steps=[("https://techcrunch.com/2025/06/25/getty-drops-key-copyright-claims-against-stability-ai-but-uk-lawsuit-continues/",
                 "early", "Getty dropped its main copyright claims; others went on"),
                ("https://siliconangle.com/2025/11/04/uk-court-mostly-sides-stability-ai-ai-copyright-lawsuit/",
                 "lost", "The High Court mostly sided with Stability AI")]),
    dict(kind="copyright", by="Getty Images", sued="Stability AI", where="US", filed="2023-02",
         about="More than 12 million photos used to train Stable Diffusion",
         steps=[("https://siliconangle.com/2023/02/06/getty-images-sues-stability-ai-copyright-trademark-infringement/",
                 "filed", "Sued in a Delaware federal court")]),
    dict(kind="copyright", by="Photographer Robert Kneschke", sued="LAION", where="Germany", filed="",
         about="A photo collected into a dataset for training AI",
         steps=[("https://the-decoder.com/german-court-allows-non-profit-laion-to-scrape-copyrighted-images-for-ai-training/",
                 "lost", "A Hamburg court ruled the non-profit could collect the images")]),
    dict(kind="copyright", by="Thomson Reuters", sued="Ross Intelligence", where="US", filed="",
         about="Legal summaries used to train a legal research AI",
         steps=[("https://the-decoder.com/us-court-rejects-ai-startups-fair-use-defence-but-impact-on-openai-and-others-may-be-limited/",
                 "won", "A federal court rejected Ross's fair use defence")]),
    dict(kind="copyright", by="Programmers (Joseph Saveri Law Firm)", sued="GitHub, Microsoft and OpenAI", where="US",
         filed="2022", about="Open-source code used to train Copilot and copied without its licence terms",
         steps=[("https://the-decoder.com/court-ruling-suggests-ai-systems-may-be-in-the-clear-as-long-as-they-dont-make-exact-copies/",
                 "early", "A California court dismissed large parts of the case")]),
    dict(kind="copyright", by="A YouTuber", sued="OpenAI", where="US", filed="2024-08",
         about="Video transcripts used to train AI",
         steps=[("https://techcrunch.com/2024/08/05/youtuber-files-class-action-suit-over-openais-scrape-of-creators-transcripts/",
                 "filed", "Sued as a class action")]),
    dict(kind="copyright", by="Disney and Universal", sued="Midjourney", where="US", filed="2025-06",
         about="Images of their characters made by AI",
         steps=[("https://techcrunch.com/2025/06/11/disney-and-universal-sue-midjourney-alleging-ai-related-copyright-infringement/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Warner Bros.", sued="Midjourney", where="US", filed="2025-09",
         about="Images of Superman, Batman and other characters made by AI",
         steps=[("https://techcrunch.com/2025/09/05/warner-bros-sues-midjourney-for-ai-images-of-superman-batman-and-other-characters/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="Disney, Universal and Warner Bros.", sued="MiniMax", where="US", filed="2025-09",
         about="Videos of their characters made by AI",
         steps=[("https://the-decoder.com/disney-universal-and-warner-bros-sue-minimax-over-ai-use-of-iconic-characters/",
                 "filed", "Sued")]),
    dict(kind="copyright", by="YouTubers", sued="Snap", where="US", filed="2026-01",
         about="Videos from research datasets used to train Snap's AI",
         steps=[("https://techcrunch.com/2026/01/26/youtubers-sue-snap-for-alleged-copyright-infringement-in-training-its-ai-models/",
                 "filed", "Sued")]),
    # privacy
    dict(kind="privacy", by="16 people (Clarkson Law Firm)", sued="OpenAI and Microsoft", where="US", filed="2023-06",
         about="Personal data scraped from the web and taken from ChatGPT users",
         steps=[("https://siliconangle.com/2023/06/29/openai-microsoft-face-new-class-action-lawsuit-chatgpt/", "filed",
                 "Sued as a class action in a San Francisco federal court")]),
    dict(kind="privacy", by="Eight people, two of them children", sued="Google", where="US", filed="2023-07",
         about="Personal information and posts used to train Bard",
         steps=[("https://the-decoder.com/tech-giants-face-lawsuits-for-using-stolen-data-in-ai-training/", "filed",
                 "Sued as a class action in a California federal court"),
                ("https://the-decoder.com/google-says-learning-isnt-stealing-in-one-of-its-ai-copyright-lawsuits/",
                 "filed", "Google asked the court to throw the case out")]),
    dict(kind="privacy", by="Illinois residents", sued="PimEyes and other face search companies", where="US",
         filed="2023-05", about="Faces collected from the internet without consent",
         steps=[("https://incidentdatabase.ai/cite/584", "filed",
                 "Sued as a class action under Illinois' biometric privacy law")]),
    dict(kind="privacy", by="A German consumer group", sued="Meta", where="Germany", filed="",
         about="Public Facebook and Instagram posts used to train AI",
         steps=[("https://the-decoder.com/meta-can-use-public-facebook-and-instagram-data-for-ai-training-german-court-rules/",
                 "out", "A higher regional court threw out its urgent request to stop Meta")]),
    dict(kind="privacy", by="Buyers of Meta's AI glasses", sued="Meta", where="US", filed="2026-03",
         about="Footage from the glasses reviewed by contract workers",
         steps=[("https://techcrunch.com/2026/03/05/meta-sued-over-ai-smartglasses-privacy-concerns-after-workers-reviewed-nudity-sex-and-other-footage/",
                 "filed", "Sued")]),
    dict(kind="privacy", by="Perplexity users", sued="Perplexity", where="US", filed="2026-04",
         about="Personal data from chats shared with Meta and Google",
         steps=[("https://the-decoder.com/perplexity-ai-sued-over-alleged-data-sharing-with-meta-and-google/", "filed",
                 "Sued as a class action")]),
    # likeness
    dict(kind="likeness", by="Voice actors Paul Skye Lehrman and Linnea Sage", sued="Lovo", where="US", filed="2024-05",
         about="Their voices cloned by AI",
         steps=[("https://the-decoder.com/voice-actors-sue-ai-company-over-alleged-unauthorized-voice-clones/", "filed",
                 "Sued")]),
    dict(kind="likeness", by="San Francisco City Attorney", sued="16 deepfake pornography websites", where="US",
         filed="2024-08", about="Nude images of real people, including children, made by AI",
         steps=[("https://the-decoder.com/san-francisco-sues-websites-over-non-consensual-ai-generated-deepfake-porn/",
                 "filed", "Sued")]),
    dict(kind="likeness", by="Actor Shilpa Shetty", sued="Those spreading AI fakes of her", where="India",
         filed="2025-11", about="Her face and identity used in AI deepfakes",
         steps=[("https://incidentdatabase.ai/cite/1321", "early",
                 "The Bombay High Court ordered the fakes taken down while the case goes on")]),
    dict(kind="likeness", by="NPR host David Greene", sued="Google", where="US", filed="2026-01",
         about="A NotebookLM voice he says copies his",
         steps=[("https://incidentdatabase.ai/cite/1386", "filed", "Sued in Santa Clara County")]),
    dict(kind="likeness", by="Journalist Julia Angwin and other writers", sued="Grammarly", where="US", filed="2026-03",
         about="Their names used for AI editors without consent",
         steps=[("https://techcrunch.com/2026/03/12/a-writer-is-suing-grammarly-for-turning-her-and-other-authors-into-ai-editors-without-consent/",
                 "filed", "Sued as a class action")]),
    dict(kind="likeness", by="Three Tennessee teenagers", sued="xAI", where="US", filed="2026-03",
         about="Sexual deepfake images of them made by Grok",
         steps=[("https://siliconangle.com/2026/03/16/teens-launch-lawsuit-xai-grok-deepfakes/", "filed", "Sued")]),
    dict(kind="likeness", by="Voice actor Kenjiro Tsuda", sued="TikTok, over an anonymous account", where="Japan",
         filed="", about="His voice cloned by AI to narrate videos",
         steps=[("https://www.engadget.com/2274521/japanese-court-rules-human-voices-are-protected-in-landmark-ai-case/",
                 "won", "A Tokyo court ruled using his voice without permission broke his publicity rights")]),
]

# Lawsuit stories checked and left out, so `python -m aipulse court` doesn't list them again: suits that aren't over
# copyright, privacy or likeness (antitrust, contracts, trade secrets, harm from chatbots, defamation, the government),
# cases over who owns AI-made work rather than against an AI maker, and stories we couldn't read to check.
LEFT_OUT = {
    "https://techcrunch.com/2025/02/24/chegg-sues-google-over-ai-search-summaries/",  # antitrust
    "https://techcrunch.com/2025/09/14/rolling-stone-owner-penske-media-sues-google-over-ai-summaries/",  # antitrust
    "https://the-decoder.com/google-defends-its-ai-generated-search-summaries-as-publishers-sue-over-lost-ad-revenue/",
    "https://www.engadget.com/2275023/judge-dismisses-lawsuits-claiming-googles-ai-overviews-siphon-web-traffic/",
    "https://the-decoder.com/berlin-court-rules-googles-ai-overviews-are-just-a-new-search-format-not-original-content/",
    "https://techcrunch.com/2023/12/15/news-publisher-files-class-action-antitrust-suit-against-google-citing-ais-harms-to-their-bottom-line/",
    "https://techcrunch.com/2025/06/04/reddit-sues-anthropic-for-allegedly-not-paying-for-training-data/",  # contract
    "https://techcrunch.com/2025/01/31/ai-startup-perplexity-sued-for-alleged-trademark-infringement/",  # trademark
    "https://the-decoder.com/a-court-battle-over-perplexitys-comet-agent-could-define-how-ai-is-allowed-to-shop-online-for-users/",
    "https://the-decoder.com/amazon-gets-court-order-blocking-perplexitys-ai-shopping-agent/",
    "https://siliconangle.com/2026/03/17/court-rules-perplexitys-ai-bots-can-stay-amazon/",
    "https://the-decoder.com/us-appeals-court-allows-perplexitys-ai-shopping-agent-back-on-amazon/",
    "https://ainowinstitute.org/news/press/as-meta-agrees-to-17b-settlement-now-is-the-time-to-regulate-ai-before-its-too-late-amba-kak",
    # couldn't read the story to check who sued whom
    "https://epic.org/the-mecrury-news-does-ai-belong-in-the-exam-room-lawsuit-alleges-california-health-care-group-violated-patient-privacy/",
    "https://techcrunch.com/2023/07/14/designers-sue-shein-over-ai-ripoffs-of-their-work/",  # not an AI maker
    "https://the-decoder.com/us-court-denies-ai-image-copyright-but-this-ruling-means-little/",  # who owns AI-made work
    "https://the-decoder.com/ai-copyright-debate-continues-as-uk-supreme-court-rules-against-ai-inventor/",
    "https://siliconangle.com/2025/03/19/court-rules-copyrighting-ai-generated-art-no-go-even-invented-software/",
    "https://the-decoder.com/supreme-court-ai-copyright-decision-sounds-sweeping-but-actually-settles-very-little/",
    "https://the-decoder.com/beijing-internet-court-grants-copyright-to-ai-generated-image/",
    "https://the-decoder.com/german-court-denies-copyright-protection-for-ai-generated-logos/",
    "https://the-decoder.com/german-court-says-its-ai-isnt-enough-to-void-copyright/",
    "https://the-decoder.com/german-court-rules-ai-comic-adaptation-of-copyrighted-photo-doesnt-violate-the-original/",
    "https://the-decoder.com/a-wuhan-court-just-made-ai-production-costs-a-legal-factor-in-copyright-infringement-cases/",
    # more stories on a step already listed, or on a case without changing where it stands
    "https://the-decoder.com/anthropics-1-5-billion-book-settlement-descends-into-chaos-as-authors-and-publishers-fight-over-who-gets-paid/",
    "https://techcrunch.com/2026/09/06/authors-push-back-as-publishers-and-agents-seek-share-of-anthropic-settlement/",
    "https://the-decoder.com/anthropics-1-5b-piracy-settlement-with-book-authors-is-a-record-loss-that-hands-ai-labs-their-biggest-legal-win/",
    "https://incidentdatabase.ai/cite/1294",
    "https://the-decoder.com/german-court-deepens-the-split-on-ai-and-copyright-with-its-latest-ruling/",
    "https://the-decoder.com/uk-judge-rules-that-ai-image-generator-stable-diffusion-is-not-an-infringing-copy/",
    "https://the-decoder.com/anthropic-settles-landmark-ai-copyright-lawsuit-for-at-least-1-5-billion/",
    "https://techcrunch.com/2025/09/05/screw-the-money-anthropics-1-5b-copyright-settlement-sucks-for-writers/",
    "https://the-decoder.com/napster-style-piracy-allegations-put-anthropic-at-risk-of-a-billion-dollar-class-action-lawsuit/",
    "https://the-decoder.com/meta-wins-over-llama-book-training-but-the-judge-warns-future-cases-could-go-differently/",
    "https://siliconangle.com/2025/06/24/judge-sides-anthropic-landmark-ai-copyright-case-orders-go-trial-piracy-claims/",
    "https://the-decoder.com/us-judge-questions-metas-claim-that-training-ai-on-copyrighted-books-is-fair-use/",
    "https://techcrunch.com/2025/02/21/court-filings-show-meta-staffers-discussed-using-copyrighted-content-for-ai-training/",
    "https://techcrunch.com/2025/02/17/what-the-us-first-major-ai-copyright-ruling-might-mean-for-ip-law/",
    "https://techcrunch.com/2025/02/14/court-filings-show-meta-paused-efforts-to-license-books-for-ai-training/",
    "https://techcrunch.com/2025/01/31/anthropic-ceo-dario-amodei-is-trying-to-duck-a-deposition-in-an-openai-copyright-lawsuit/",
    "https://techcrunch.com/2025/01/14/meta-execs-obsessed-over-beating-openais-gpt-4-internally-court-filings-reveal/",
    "https://techcrunch.com/2024/11/22/openai-accidentally-deleted-potential-evidence-in-ny-times-copyright-lawsuit/",
    "https://incidentdatabase.ai/cite/1004",
    "https://siliconangle.com/2024/08/13/judge-rules-artists-copyright-claims-ai-companies-can-proceed/",
    "https://techcrunch.com/2024/06/25/the-riaas-lawsuit-against-generative-music-startups-will-be-the-bloodbath-ai-needs/",
    "https://siliconangle.com/2024/04/30/group-us-newspapers-sues-open-ai-microsoft-copyright-infringement/",
    "https://siliconangle.com/2024/02/27/openai-court-new-york-times-lawsuit-used-evidence-obtained-hacking/",
    "https://the-decoder.com/openai-says-the-new-york-times-lawsuit-is-without-merit-heres-why/",
    "https://incidentdatabase.ai/cite/995",
    "https://the-decoder.com/news-media-alliance-backs-new-york-times-in-ai-copyright-lawsuit-against-openai-and-microsoft/",
    "https://the-decoder.com/openai-and-microsoft-slapped-with-another-lawsuit-for-stealing-authors-works/",
    "https://the-decoder.com/openai-apparently-going-all-in-on-chatgpt-copyright-lawsuit/",
    "https://epic.org/cyberscoop-openai-lawsuit-reignites-privacy-debate-over-data-scraping/",
    "https://the-decoder.com/authors-sue-meta-and-openai-for-possible-ai-copyright-infringement/",
    "https://epic.org/rolling-stone-new-chatgpt-lawsuits-may-be-start-of-ais-legal-sh-tstorm/",
    # not a lawsuit over copyright, privacy or likeness against an AI maker
    "https://techcrunch.com/2026/09/02/openai-faces-30-more-lawsuits-tied-to-tumbler-ridge-shooting/",
    "https://epic.org/huffpost-ice-observers-sue-trump-administration-alleging-surveillance-and-retaliation/",
    "https://techcrunch.com/2026/07/13/the-wildest-allegations-in-apples-trade-secrets-lawsuit-against-openai/",
    "https://www.marktechpost.com/2026/06/08/clawhub-security-signals-a-coding-guide-to-end-to-end-security-signal-analysis-and-verdict-classification-on-the-ai-skills-dataset/",
    "https://the-decoder.com/musk-and-altman-face-off-in-court-over-openais-for-profit-pivot/",
    "https://the-decoder.com/after-groks-deepfake-flood-senate-passes-bill-letting-victims-take-creators-to-court/",
    "https://techcrunch.com/2026/01/08/elon-musks-lawsuit-against-openai-will-face-a-jury-in-march/",
    "https://incidentdatabase.ai/cite/1346",
    "https://the-decoder.com/columbia-university-launches-tracker-for-ai-deals-and-lawsuits-from-media-companies/",
    "https://incidentdatabase.ai/cite/1682",
    "https://incidentdatabase.ai/cite/1576",
    "https://techcrunch.com/2025/06/07/lawyers-could-face-severe-penalties-for-fake-ai-generated-citations-uk-court-warns/",
    "https://incidentdatabase.ai/cite/1257",
    "https://www.marktechpost.com/2025/05/26/can-llms-really-judge-with-reasoning-microsoft-and-tsinghua-researchers-introduce-reward-reasoning-models-to-dynamically-scale-test-time-compute-for-better-alignment/",
    "https://www.marktechpost.com/2025/03/14/patronus-ai-introduces-the-industrys-first-multimodal-llm-as-a-judge-mllm-as-a-judge-designed-to-evaluate-and-optimize-ai-systems-that-convert-image-inputs-into-text-outputs/",
    "https://incidentdatabase.ai/cite/1577",
    "https://www.marktechpost.com/2025/01/12/meta-ai-introduces-clue-constitutional-mllm-judge-an-ai-framework-designed-to-address-the-shortcomings-of-traditional-image-safety-systems/",
    "https://techcrunch.com/2025/01/10/hugging-face-settles-suit-with-ai-startup-friendliai-which-had-accused-it-of-patent-infringement/",
    "https://incidentdatabase.ai/cite/855",
    "https://techcrunch.com/2024/11/15/x-sues-to-block-california-anti-deepfakes-bill/",
    "https://epic.org/epic-privacy-lawsuit-against-clearview-ai-is-about-protecting-peoples-rights-not-silencing-clearview-ais-speech/",
    "https://techcrunch.com/2024/10/29/margaret-atwoods-verdict-on-ai-poetry-is-in-and-its-not-good/",
    "https://techcrunch.com/2024/10/02/judge-blocks-californias-new-ai-law-in-case-over-kamala-harris-deepfake-musk-reposted/",
    "https://incidentdatabase.ai/cite/807",
    "https://the-decoder.com/uk-cracks-down-on-deepfake-abuse-with-court-ruling-and-new-law/",
    "https://the-decoder.com/pixel-manipulation-sabotage-lawsuits-how-artists-fight-generative-ai-for-images/",
    "https://epic.org/reuters-hi-retailer-chatbot-lawsuits-rely-on-california-cold-war-wiretap-law/",
    "https://epic.org/black-enterprise-detroit-police-sued-again-for-reckless-use-of-facial-recognition-technology/",
    "https://techcrunch.com/2023/10/06/some-gen-ai-vendors-say-theyll-defend-customers-from-ip-lawsuits-others-not-so-much/",
    "https://the-decoder.com/authors-guild-threatens-leading-ai-companies-with-another-copyright-lawsuit/",
    "https://the-decoder.com/ai-copyright-far-from-settled-as-japan-and-israel-stake-out-early-positions/",
    "https://techcrunch.com/2023/05/31/amazon-settles-with-ftc-for-25m-after-flouting-kids-privacy-and-deletion-requests/",
}

# a headline about a lawsuit or a court ruling
SUIT = re.compile(r"\blawsuits?\b|\bsues?\b|\bsued\b|\bsuing\b|class action|\bcourt\b(?!room)|\bjudge\b(?! models?)|"
                  r"\bruling\b|\bsettle(s|d|ment)?\b(?! on)|\bverdict\b", re.I)
# ...over copyright, privacy or likeness
TOPIC = re.compile(r"copyright|fair use|piracy|pirated|authors?|books?|publishers?|lyrics|songs?|music|artists?|"
                   r"images?|photos?|training|privacy|personal data|biometric|facial|face|voice|likeness|deepfakes?|"
                   r"publicity|scrap\w+|newspapers?|news (agency|companies|outlets)", re.I)
# Our own flat picture beside the title: a courthouse with the scales of justice, a gavel on its block, and a filed
# page with a chip on it. No real people, buildings or logos.
HERO = ('<svg class="ct-art" viewBox="14 24 310 172" role="img" aria-label="A courthouse, a gavel and a filed page">'
        '<g stroke="#1B1F24" stroke-width="3" stroke-linejoin="round" fill="#F4EFE6">'
        '<path d="M66 72 160 30 254 72Z"/><rect x="60" y="72" width="200" height="12"/>'
        '<rect x="76" y="84" width="16" height="66"/><rect x="114" y="84" width="16" height="66"/>'
        '<rect x="190" y="84" width="16" height="66"/><rect x="228" y="84" width="16" height="66"/>'
        '<rect x="56" y="150" width="208" height="9"/><rect x="46" y="159" width="228" height="9"/></g>'
        '<g stroke="#1B1F24" stroke-width="2.5" fill="none" stroke-linecap="round">'
        '<path d="M160 40v26M144 47h32M144 47l-6 11M144 47l6 11M176 47l-6 11M176 47l6 11M152 66h16"/>'
        '<path d="M137 58a7 4 0 0 0 14 0ZM169 58a7 4 0 0 0 14 0Z" fill="#E69F00"/></g>'
        '<g stroke="#1B1F24" stroke-width="3" stroke-linejoin="round">'
        '<g transform="rotate(-8 52 158)"><rect x="22" y="122" width="56" height="70" rx="3" fill="#fff"/>'
        '<path d="M31 136h38M31 146h38M31 156h24" stroke-width="2.5"/>'
        '<rect x="50" y="164" width="18" height="18" rx="2" fill="#E69F00" stroke-width="2.5"/></g>'
        '<rect x="226" y="174" width="70" height="14" rx="3" fill="#B5793C"/>'
        '<g transform="rotate(-30 262 150)"><rect x="257" y="146" width="62" height="9" rx="4" fill="#D9A066"/>'
        '<rect x="232" y="132" width="30" height="38" rx="5" fill="#B5793C"/></g></g></svg>')

QUESTION = "Who is taking AI companies to court, and where does each case stand?"
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _month(ym: str) -> str:
    """'2024-11' → 'Nov 2024'; a bare year stays as it is."""
    if len(ym) == 7:
        y, m = ym.split("-")
        return f"{_MONTHS[int(m) - 1]} {y}"
    return ym


def _day(d: str) -> str:
    day = date.fromisoformat(d)
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def cases(cards: list[dict]) -> list[dict]:
    """The cases in CASES with the steps whose story we have, each step with its story (title, source, date, url),
    oldest step first; the case's status is its latest step's. Cases with no story left are dropped."""
    by_url = {s["url"]: s | {"date": s.get("date") or c["date"]} for c in cards for s in [c, *(c.get("also") or [])]}
    out = []
    for case in CASES:
        steps = [dict(url=u, status=st, what=w, title=s["title"].strip(), source=s["source"], date=s["date"])
                 for u, st, w in case["steps"] if (s := by_url.get(u))]
        if steps:
            steps.sort(key=lambda s: s["date"])
            out.append(case | {"steps": steps, "status": steps[-1]["status"], "latest": steps[-1]["date"]})
    return sorted(out, key=lambda c: c["latest"], reverse=True)


def candidates(cards: list[dict], since: str = SINCE) -> list[dict]:
    """Lawsuit stories from `since` that no case's steps use and LEFT_OUT doesn't hold: one per event, newest first."""
    used = {u for case in CASES for u, *_ in case["steps"]} | LEFT_OUT
    out = []
    for c in sorted(cards, key=lambda c: c["date"], reverse=True):  # a card is one event, its other stories in "also"
        if c["date"] < since or c["category"] == "research":
            continue
        if any(s["url"] in used for s in [c, *(c.get("also") or [])]):
            continue
        if SUIT.search(c["title"]) and TOPIC.search(c["title"] + " " + (c.get("summary") or "")[:300]):
            out.append(c)
    return out


# steps where a court decided something: a gavel on the timeline instead of a dot
RULINGS = {"early", "won", "lost", "out"}


def _chip(status: str) -> str:
    label, colour, _ = STATUSES[status]
    return f'<span class="ct-st" style="--c:{colour}">{escape(label)}</span>'


def _cards(rows: list[dict]) -> str:
    """A kind's cases as docket cards in newspaper columns: where it stands up top (a stamp once it has ended), the
    case caption (who is suing v. who is sued), what it's about, then its steps on a small timeline, each dot in the
    colour of where it left the case (a gavel where a court decided something), with its date and source."""
    def card(c: dict) -> str:
        label, colour, is_open = STATUSES[c["status"]]
        steps = "".join(f'<li{" class=ct-rule" * (s["status"] in RULINGS)} style="--c:{STATUSES[s["status"]][1]}">'
                        f'<span class="ct-d">{_day(s["date"])}</span>'
                        f'{escape(s["what"])}. <a href="{escape(s["url"])}" rel="noopener">{escape(s["source"])}</a></li>'
                        for s in c["steps"])
        meta = escape(c["where"]) + (f' · filed {escape(_month(c["filed"]))}' if c["filed"] else "")
        mark = _chip(c["status"]) if is_open else f'<span class="ct-stamp">{escape(label)}</span>'
        return (f'<article class="ct-card" style="--c:{colour}"><div class="ct-top">{mark}'
                f'<span class="ct-meta">{meta}</span></div>'
                f'<div class="ct-cap"><span class="ct-side">Suing</span><b>{escape(c["by"])}</b>'
                f'<i>v.</i><span class="ct-side">Sued</span><b>{escape(c["sued"])}</b></div>'
                f'<p class="ct-about">{escape(c["about"])}</p><ol class="ct-track">{steps}</ol></article>')
    return f'<div class="ct-cards">{"".join(card(c) for c in rows)}</div>'


def _board(rows: list[dict], under: str = "") -> str:
    """Where the cases stand: an Open panel and an Ended panel, a row per status with a dot per case (its case on
    hover) and the count; the few ended cases are named under their row. `under` goes below the Open panel."""
    def panel(is_open: bool) -> str:
        group = [c for c in rows if STATUSES[c["status"]][2] == is_open]
        out = ""
        for k, (label, colour, o) in STATUSES.items():
            cs = [c for c in group if c["status"] == k]
            if o != is_open or not cs:
                continue
            dots = "".join(f'<i title="{escape(c["by"])} v {escape(c["sued"])}"></i>' for c in cs)
            names = ("" if is_open else '<div class="ct-names">'
                     + " · ".join(f'{escape(c["by"])} v {escape(c["sued"])}' for c in cs) + "</div>")
            out += (f'<div class="ct-row" style="--c:{colour}"><div class="ct-lab">{escape(label)}</div>'
                    f'<div class="ct-dots">{dots}</div><div class="ct-n">{len(cs)}</div>{names}</div>')
        head, means = (("Open", "Filed, an early ruling, or some of those suing settled") if is_open
                       else ("Ended", "Decided, settled or thrown out"))
        return (f'<div class="ct-panel"><div class="ct-head"><b>{len(group)}</b> {head}'
                f'<span>{means}</span></div>{out}</div>')
    note = '<p class="jb-note">A dot is a case, placed by its latest step; hover a dot for the case.</p>'
    return f'<div class="ct-board"><div>{panel(True)}{note}{under}</div>{panel(False)}</div>'


def _limits(rows: list[dict]) -> str:
    """About these counts, as a small table: what each count is made of."""
    first = min(rows, key=lambda c: c["steps"][0]["date"])["steps"][0]["date"][:4]
    limits = [
        (f"{len(rows)} cases from the news we read",
         f"Lawsuits against AI makers over copyright, privacy or likeness that outlets we read reported since {first}. "
         "Cases that were joined together in court may appear as the separate suits the news reported."),
        ("Where a case stands",
         "Its latest step in the news we read, with the date. A case counts as open until a story reports a decision, "
         "a settlement or that it was thrown out."),
        ("A decision isn't always the end",
         "Decided cases can be appealed; an appeal is added as a new step once reported."),
        ("Left out",
         "Lawsuits over competition, contracts, trade secrets or harm done by chatbots, and cases over who owns "
         "AI-made work."),
    ]
    body = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
    return ('<section class="jb-lim"><h2>About these counts</h2>\n'
            f'<table class="mt jb-small jb-limits"><tbody>{body}</tbody></table></section>\n')


def page_body(rows: list[dict]) -> str:
    """The page under the masthead: where the cases stand, the cases by country, then each kind's cases, open first,
    and what the counts are made of. Every number is worked out from the rows."""
    open_ = [c for c in rows if STATUSES[c["status"]][2]]
    countries = sorted({c["where"] for c in rows}, key=lambda w: (-sum(c["where"] == w for c in rows), w))
    first = min(c["steps"][0]["date"][:4] for c in rows)
    intro = (f"{len(rows)} lawsuits against AI makers over copyright, privacy and people's likeness, in "
             f"{len(countries)} countries, reported since {first}. {len(open_)} are open. Each case shows its steps "
             "as the news reported them; new steps are added once checked.")
    where = "".join(f'<tr><td>{escape(w)}</td><td class="n">{sum(c["where"] == w for c in rows)}</td>'
                    f'<td class="n">{sum(c["where"] == w for c in open_)}</td></tr>' for w in countries)
    kinds = "".join(f'<tr><td>{escape(label)}</td><td class="n">{sum(c["kind"] == k for c in rows)}</td>'
                    f'<td class="n">{sum(c["kind"] == k for c in open_)}</td></tr>'
                    for k, (label, _) in KINDS.items() if any(c["kind"] == k for c in rows))
    small = ('<div class="jb-split ct-small">'
             '<table class="mt jb-small"><thead><tr><th>Court in</th><th>Cases</th><th>Open</th></tr></thead>'
             f'<tbody>{where}</tbody></table>'
             '<table class="mt jb-small"><thead><tr><th>About</th><th>Cases</th><th>Open</th></tr></thead>'
             f'<tbody>{kinds}</tbody></table></div>')
    sections = ""
    for k, (label, means) in KINDS.items():
        group = [c for c in rows if c["kind"] == k]
        if group:
            group.sort(key=lambda c: c["latest"], reverse=True)
            group.sort(key=lambda c: not STATUSES[c["status"]][2])  # open first, each part newest step first
            n_open = sum(STATUSES[c["status"]][2] for c in group)
            sections += (f'<section class="ct-kind"><h3>{escape(label)} <span>{len(group)} case{"s" * (len(group) != 1)}'
                         f' · {n_open} open</span></h3>\n<p>{escape(means)} Open cases first, newest step first.</p>\n'
                         f'{_cards(group)}'
                         '</section>\n')
    return (f'<div class="ft jb ct">\n<div class="ct-hero"><div><h1>AI in court</h1>\n'
            f'<p class="jb-q">{escape(QUESTION)}</p>\n<p class="intro">{escape(intro)}</p></div>{HERO}</div>\n'
            f'<section class="jb-answer"><h2>Where the cases stand</h2>\n'
            f'{_board(rows, small)}</section>\n'
            f'<h2>Each case</h2>\n{sections}{_limits(rows)}</div>\n')


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write ai-in-court/. Returns its path."""
    rows = cases(cards)
    (out / PATH).mkdir(parents=True, exist_ok=True)
    what = (f"{QUESTION} Lawsuits against AI makers over copyright, privacy and likeness, in several countries, each "
            "with its steps as the news reported them.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI in court",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH / "index.html").write_text(
        pages.page("AI in court · AI Pulse", what, PATH, page_body(rows), data, pages.frame(conn, len(cards)),
                   ("/industry/", "Back to Industry"),
                   "Headlines are the outlets' own, each linking to its story. New cases and steps are added once "
                   "checked by hand."),
        encoding="utf-8")
    return [PATH]
