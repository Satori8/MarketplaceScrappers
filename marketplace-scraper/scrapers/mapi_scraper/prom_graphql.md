# Prom.ua GraphQL Master Specification (MAPI)
# Version: 1.1.0 (Literal Payloads)
# Date: 2026-05-17
# Role: Technical Reference for AI Agents to construct and parse GQL requests.

---

## 1. Core Listing Operations (Standard Products)
All these operations share a common selection set for the `product` object.

### A. CategoryListingQuery
**Purpose**: Browsing by category slug.
```graphql
query CategoryListingQuery($alias: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String) {
  listing: categoryListing(alias: $alias, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}) {
    category { 
      id 
      caption 
      __typename 
    }
    page { 
      total 
      products { 
        product { 
          id 
          name: nameForCatalog 
          sku 
          price 
          discountedPrice 
          priceCurrency 
          priceCurrencyLocalized 
          urlText 
          categoryId 
          categoryIds 
          image(width: 200, height: 200) 
          presence { 
            presence 
            isAvailable 
            __typename 
          } 
          company { 
            id 
            name 
            slug 
            opinionStats { 
              opinionPositivePercent 
              opinionTotal 
              __typename 
            } 
            __typename 
          } 
          category { 
            id 
            caption 
            __typename 
          } 
          manufacturerInfo { 
            id 
            name 
            __typename 
          } 
          catalogPresence { 
            title 
            __typename 
          } 
          __typename 
        } 
        __typename 
      } 
      __typename 
    } 
    __typename 
  } 
}
```

### B. SearchListingQuery
**Purpose**: Keyword search.
```graphql
query SearchListingQuery($search_term: String!, $params: Any, $offset: Int, $limit: Int, $regionId: Int, $subdomain: String) {
  listing: searchListing(search_term: $search_term, params: $params, offset: $offset, limit: $limit, region: {id: $regionId, subdomain: $subdomain}) {
    page { 
      total 
      products { 
        product { 
          id 
          name: nameForCatalog 
          sku 
          price 
          discountedPrice 
          priceCurrency 
          priceCurrencyLocalized 
          urlText 
          categoryId 
          categoryIds 
          image(width: 200, height: 200) 
          presence { 
            presence 
            isAvailable 
            __typename 
          } 
          company { 
            id 
            name 
            slug 
            opinionStats { 
              opinionPositivePercent 
              opinionTotal 
              __typename 
            } 
            __typename 
          } 
          category { 
            id 
            caption 
            __typename 
          } 
          manufacturerInfo { 
            id 
            name 
            __typename 
          } 
          catalogPresence { 
            title 
            __typename 
          } 
          __typename 
        } 
        __typename 
      } 
      __typename 
    } 
    __typename 
  } 
}
```

### C. CompanyListingQuery & ManufacturerListingQuery
*Note: Same selection set as above, using `companyListing(company_id: $company_id, ...)` or `manufacturerListing(alias: $alias, ...)` as the root field.*

---

## 2. Enrichment & Intelligence (Literal Bodies)

### A. CompanyContactsQuery
**Purpose**: Extract direct merchant contact info (Phones, Emails, Address).
```graphql
query CompanyContactsQuery($company_id: Int!, $groupId: Int!, $productId: Long!, $withGroupManagerPhones: Boolean = false, $withWorkingHoursWarning: Boolean = false, $getProductDetails: Boolean = false) {
  context {
    context_meta
    currentRegionId
    recaptchaToken
    __typename
  }
  company(id: $company_id) {
    ...CompanyWorkingHoursFragment @include(if: $withWorkingHoursWarning)
    ...CompanyRatingFragment
    id
    name
    contactPerson
    contactEmail
    phones {
      id
      description
      number
      __typename
    }
    addressText
    isChatVisible
    mainLogoUrl(width: 120, height: 120)
    slug
    isOneClickOrderAllowed
    isOrderableInCatalog
    isPackageCPA
    addressMapDescription
    region {
      id
      __typename
    }
    geoCoordinates {
      id
      latitude
      longtitude
      __typename
    }
    branches {
      id
      name
      phones
      address {
        region_id
        country_id
        city
        zipCode
        street
        regionText
        __typename
      }
      __typename
    }
    webSiteUrl
    site {
      id
      isDisabled
      __typename
    }
    operationType
    showSiteContacts
    __typename
  }
  productGroup(id: $groupId) @include(if: $withGroupManagerPhones) {
    id
    managerPhones {
      id
      number
      __typename
    }
    __typename
  }
  product(id: $productId) @include(if: $getProductDetails) {
    id
    name
    image(width: 60, height: 60)
    price
    signed_id
    discountedPrice
    priceCurrencyLocalized
    buyButtonDisplayType
    regions {
      id
      name
      isCity
      __typename
    }
    productAdvert {
      commission_type
      showPhoneToken
      __typename
    }
    __typename
  }
}

fragment CompanyWorkingHoursFragment on Company {
  id
  isWorkingNow
  isOrderableInCatalog
  scheduleSettings {
    id
    currentDayCaption
    __typename
  }
  scheduleDays {
    id
    name
    dayType
    hasBreak
    workTimeRangeStart
    workTimeRangeEnd
    breakTimeRangeStart
    breakTimeRangeEnd
    __typename
  }
  __typename
}

fragment CompanyRatingFragment on Company {
  id
  inTopSegment
  segmentBehindNew
  isService
  opinionStats {
    id
    opinionPositivePercent
    opinionTotal
    __typename
  }
  combinedOpinionStats {
    id
    opinionPositivePercent
    opinionTotal
    __typename
  }
  __typename
}
```

### B. CompanyFiltersQuery
**Purpose**: Discovery of available filters for a merchant's listing.
```graphql
query CompanyFiltersQuery($company_id: Int!, $params: Any, $sort: String, $regionId: Int = null, $subdomain: String = null) {
  listing: companyListing(
    company_id: $company_id
    params: $params
    sort: $sort
    region: {id: $regionId, subdomain: $subdomain}
  ) {
    filters {
      ...FiltersFragment
      __typename
    }
    __typename
  }
}

fragment FiltersFragment on ListingFilters {
  total
  priceChartFilter {
    ...PriceFilterFragment
    __typename
  }
  binaryFilters {
    ...PromoBinaryFilterFragment
    __typename
  }
  attributeFilters {
    ...AttributeFilterFragment
    __typename
  }
  categoryFilter {
    ...AttributeFilterFragment
    __typename
  }
  productGroupFilter {
    ...AttributeFilterFragment
    __typename
  }
  deliveryFilter {
    ...DeliveryFilterFragment
    __typename
  }
  colorFilter {
    ...AttributeFilterFragment
    __typename
  }
  promoFilter {
    ...ItemPromoFilterFragment
    __typename
  }
  regionFilter {
    ...RegionFilterFragment
    __typename
  }
  regionDeliveryFilter {
    ...RegionFilterFragment
    __typename
  }
  opinionsFilter {
    ...ProductOpinionsFilterFragment
    __typename
  }
  __typename
}

fragment PriceFilterFragment on PriceChartFilter {
  measureUnit
  values
  __typename
}

fragment PromoBinaryFilterFragment on Filter {
  name
  values {
    selected
    value
    count
    title
    icon
    darkIcon
    displayType
    image {
      src
      srcDark
      width
      height
      altText
      __typename
    }
    __typename
  }
  __typename
}

fragment AttributeFilterFragment on AttributeFilter {
  name
  title
  type
  min
  max
  measureUnit
  values {
    position
    positionInPreview
    selected
    value
    count
    title
    position
    parent
    used_count
    colorHex
    __typename
  }
  __typename
}

fragment DeliveryFilterFragment on Filter {
  name
  values {
    selected
    value
    count
    title
    __typename
  }
  __typename
}

fragment ProductOpinionsFilterFragment on Filter {
  name
  title
  values {
    selected
    value
    count
    title
    __typename
  }
  __typename
}

fragment ItemPromoFilterFragment on Filter {
  name
  values {
    selected
    value
    count
    title
    icon
    darkIcon
    __typename
  }
  __typename
}

fragment RegionFilterFragment on Filter {
  title
  name
  values {
    selected
    value
    count
    title
    groupName
    __typename
  }
  __typename
}
```

### C. MegaMenuQuery
**Purpose**: Crawl the entire category structure.
```graphql
query MegaMenuQuery($type: String = "C") {
  megamenu(type: $type) {
    categories {
      categoryId
      alias
      caption
      parentId
      verticalDomain
      children {
        categoryId
        alias
        caption
        parentId
        verticalDomain
        children {
          categoryId
          alias
          caption
          parentId
          verticalDomain
          __typename
        }
        __typename
      }
      __typename
    }
    smartCats {
      id
      alias
      caption
      url
      __typename
    }
    catalogTypesLink {
      id
      alias
      caption
      url
      __typename
    }
    __typename
  }
}
```

---

## 3. Reference Header Template
```http
POST /graphql HTTP/1.1
Content-Type: application/json
x-language: uk
x-requested-with: XMLHttpRequest
x-apollo-operation-name: [OperationName]
Referer: https://prom.ua/
Origin: https://prom.ua
```

---

## 4. Normalization & Data Mapping (Output Schema)

AI agents should use the following JSON paths to extract key data for database enrichment:

### A. Merchant Contacts (from `CompanyContactsQuery`)
| Field | JSON Path (relative to `data`) | Description |
| :--- | :--- | :--- |
| **Email** | `company.contactEmail` | Direct business email. |
| **Phones** | `company.phones` (Array) | Iterate and extract `number`. |
| **Address** | `company.addressText` | Formatted physical address. |
| **Website** | `company.webSiteUrl` | External merchant website. |
| **Coordinates**| `company.geoCoordinates` | Object with `latitude` and `longtitude`. |
| **Branches** | `company.branches` (Array) | Additional branch phones and addresses. |
| **Rating** | `company.opinionStats.opinionPositivePercent`| Merchant reliability score. |

### B. Standard Product Data (from Listings)
| Field | JSON Path (relative to `listing.page.products[i].product`) | Description |
| :--- | :--- | :--- |
| **Price** | `discountedPrice` ?? `price` | Reduced price if available. |
| **SKU** | `sku` | Merchant specific SKU. |
| **Merchant ID**| `company.id` | Used to link with `CompanyContactsQuery`. |
| **Category** | `category.caption` | Standard category name. |

### C. Category Tree (from `MegaMenuQuery`)
- Iterate `data.megamenu.categories`.
- For each category, recursively process `children` to build the full taxonomic tree.
- Map `categoryId`, `alias`, and `caption`.
