# ECOBUD Workflow

## Product Description Flow

1. Collect raw product specs.
2. Normalize into canonical fields.
3. Validate critical facts:
   - voltage
   - amperage
   - power
   - warranty
   - country/brand
   - compatibility
   - sensor type
4. Generate descriptions:
   - Prom.ua: SEO article style.
   - ROZETKA: concise conversion facts.
   - Epicentr: indexed installation/compatibility detail.
   - Allo: technical passport plus benefits.
5. Generate short descriptions:
   - Epicentr version.
   - ROZETKA version.
6. Human-check for factual accuracy and marketplace restrictions.

## Inputs Needed

- Product name
- Brand
- Category
- Technical specs
- Compatibility
- Warranty/service
- Installation notes
- Marketplace constraints
- Keywords

## Output Files

Use this naming pattern:

```text
YYYY-MM-DD product-name marketplace-output.md
```

