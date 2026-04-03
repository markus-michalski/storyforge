# State Schema

## Cache Location
`~/.storyforge/cache/state.json`

## Schema

```json
{
  "schema_version": "1.0.0",
  "plugin_version": "0.1.0-dev",
  "built_at": "2026-04-03T12:00:00+00:00",
  "config": { "...loaded config..." },

  "books": {
    "<book-slug>": {
      "slug": "my-horror-novel",
      "title": "My Horror Novel",
      "author": "dark-narrator",
      "genres": ["horror", "supernatural"],
      "book_type": "novel",
      "status": "Drafting",
      "language": "en",
      "target_word_count": 80000,
      "series": "",
      "series_number": 0,
      "description": "...",
      "created": "2026-04-03",
      "updated": "2026-04-03",
      "chapter_count": 25,
      "total_words": 42000,
      "chapters_data": {
        "01-the-awakening": {
          "slug": "01-the-awakening",
          "title": "The Awakening",
          "number": 1,
          "status": "Final",
          "pov_character": "Alex",
          "word_count": 3200,
          "has_draft": true
        }
      },
      "characters": {
        "alex": {
          "slug": "alex",
          "name": "Alex",
          "role": "protagonist",
          "status": "Arc Defined"
        }
      },
      "character_count": 5
    }
  },

  "authors": {
    "<author-slug>": {
      "slug": "dark-narrator",
      "name": "Dark Narrator",
      "primary_genres": ["horror", "dark-fantasy"],
      "narrative_voice": "first-person",
      "tense": "past",
      "tone": ["sarcastic", "atmospheric"],
      "sentence_style": "varied",
      "vocabulary_level": "moderate",
      "dialog_style": "naturalistic",
      "pacing": "tension-driven",
      "themes": ["isolation", "cosmic-dread"],
      "influences": ["Stephen King", "Clive Barker"],
      "avoid": ["purple-prose", "info-dumps"],
      "studied_works_count": 3
    }
  },

  "series": {
    "<series-slug>": {
      "slug": "darkness-chronicles",
      "title": "Darkness Chronicles",
      "genres": ["horror", "supernatural"],
      "planned_books": 3,
      "status": "Planning",
      "description": "..."
    }
  },

  "ideas": [
    {
      "title": "Vampire Coffee Shop",
      "notes": "**Genres:** lgbtq, supernatural\n\nA vampire opens a night-only coffee shop..."
    }
  ],

  "session": {
    "last_book": "my-horror-novel",
    "last_chapter": "01-the-awakening",
    "last_phase": "Drafting",
    "active_author": "dark-narrator"
  }
}
```

## Rebuild Behavior

- State is rebuilt from filesystem when cache is stale (mtime check)
- Session data is preserved across rebuilds
- Rebuild triggered by: config change, manual `rebuild_state()`, cache file missing
