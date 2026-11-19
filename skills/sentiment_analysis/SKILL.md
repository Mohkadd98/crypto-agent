---
name: sentiment_analysis
display_name: Sentiment Analysis
description: Analyzes social sentiment and news sentiment
version: 1.0.0
dependencies: ["market_scanner"]
required_apis: ["twitter", "reddit", "newsapi", "lunarcrush"]
available_tools: []
priority: 11
is_core: false
config:
  sources: ["twitter", "reddit", "news", "lunarcrush"]
  min_mentions: 10
---

# Sentiment Analysis Skill

Analyzes social media and news sentiment for cryptocurrency market intelligence.

## Capabilities

- **Social Sentiment**: Twitter, Reddit, Discord mention volume and sentiment
- **News Sentiment**: Financial news, blog posts, announcements sentiment
- **Fear & Greed Index**: Market emotion indicators
- **Influencer Tracking**: Key opinion leader mentions and stance
- **Narrative Detection**: Emerging narratives and sector rotation
- **Sentiment Divergence**: Price vs sentiment discrepancies

## Tools

*Note: Tools to be implemented with API integrations*

### analyze_social_sentiment
- Parameters: symbol, sources, timeframe

### analyze_news_sentiment
- Parameters: symbol, sources, timeframe

## Usage Examples

```
"What's the sentiment on SOL right now?"
"Show me fear/greed index for crypto"
"Track influencer mentions for new AI tokens"
"Detect sentiment divergence on BTC"
"Analyze Reddit sentiment for meme coins"
```

## Data Sources

- **Twitter/X**: Tweet volume, engagement, sentiment (requires Twitter API v2)
- **Reddit**: Subreddit mentions, comment sentiment, upvote ratios
- **NewsAPI**: Financial news headlines, article sentiment
- **LunarCrush**: Social metrics, galaxy score, alt rank
- **Santiment**: Social volume, sentiment, holder distribution

## Metrics

- **Sentiment Score**: -1 (bearish) to +1 (bullish)
- **Mention Volume**: Absolute and relative to average
- **Engagement Rate**: Likes/retweets/replies per mention
- **Influencer Alignment**: % of key accounts bullish/bearish
- **Sentiment Trend**: 24h, 7d, 30d direction

## Integration

Enhances technical_analysis with sentiment confirmation. Used by risk_analysis for sentiment risk factor. Feeds breakout_detection for sentiment-fueled moves.