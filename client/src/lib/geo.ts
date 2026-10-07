/**
 * Geographic Data Dictionary, ISO 3166-1 Alpha-2 Country Catalog,
 * Hierarchical Subdivisions (States/Provinces/Territories), and
 * Country-Specific Postal/ZIP Code Validation Rules.
 */

export interface CountryItem {
  code: string;
  name: string;
  isSupported: boolean;
  postalFormatDesc: string;
  postalPlaceholder: string;
}

export interface SubdivisionItem {
  code: string;
  name: string;
}

export const SUPPORTED_COUNTRY_CODE = 'US';
export const DEFAULT_COUNTRY_NAME = 'United States of America';

/**
 * US States (50), Federal District (DC), and Outlying Territories (5).
 * Display format: "State Name (XX)"
 */
export const US_SUBDIVISIONS: SubdivisionItem[] = [
  { code: 'AL', name: 'Alabama' },
  { code: 'AK', name: 'Alaska' },
  { code: 'AZ', name: 'Arizona' },
  { code: 'AR', name: 'Arkansas' },
  { code: 'CA', name: 'California' },
  { code: 'CO', name: 'Colorado' },
  { code: 'CT', name: 'Connecticut' },
  { code: 'DE', name: 'Delaware' },
  { code: 'FL', name: 'Florida' },
  { code: 'GA', name: 'Georgia' },
  { code: 'HI', name: 'Hawaii' },
  { code: 'ID', name: 'Idaho' },
  { code: 'IL', name: 'Illinois' },
  { code: 'IN', name: 'Indiana' },
  { code: 'IA', name: 'Iowa' },
  { code: 'KS', name: 'Kansas' },
  { code: 'KY', name: 'Kentucky' },
  { code: 'LA', name: 'Louisiana' },
  { code: 'ME', name: 'Maine' },
  { code: 'MD', name: 'Maryland' },
  { code: 'MA', name: 'Massachusetts' },
  { code: 'MI', name: 'Michigan' },
  { code: 'MN', name: 'Minnesota' },
  { code: 'MS', name: 'Mississippi' },
  { code: 'MO', name: 'Missouri' },
  { code: 'MT', name: 'Montana' },
  { code: 'NE', name: 'Nebraska' },
  { code: 'NV', name: 'Nevada' },
  { code: 'NH', name: 'New Hampshire' },
  { code: 'NJ', name: 'New Jersey' },
  { code: 'NM', name: 'New Mexico' },
  { code: 'NY', name: 'New York' },
  { code: 'NC', name: 'North Carolina' },
  { code: 'ND', name: 'North Dakota' },
  { code: 'OH', name: 'Ohio' },
  { code: 'OK', name: 'Oklahoma' },
  { code: 'OR', name: 'Oregon' },
  { code: 'PA', name: 'Pennsylvania' },
  { code: 'RI', name: 'Rhode Island' },
  { code: 'SC', name: 'South Carolina' },
  { code: 'SD', name: 'South Dakota' },
  { code: 'TN', name: 'Tennessee' },
  { code: 'TX', name: 'Texas' },
  { code: 'UT', name: 'Utah' },
  { code: 'VT', name: 'Vermont' },
  { code: 'VA', name: 'Virginia' },
  { code: 'WA', name: 'Washington' },
  { code: 'WV', name: 'West Virginia' },
  { code: 'WI', name: 'Wisconsin' },
  { code: 'WY', name: 'Wyoming' },
  { code: 'DC', name: 'District of Columbia' },
  { code: 'AS', name: 'American Samoa' },
  { code: 'GU', name: 'Guam' },
  { code: 'MP', name: 'Northern Mariana Islands' },
  { code: 'PR', name: 'Puerto Rico' },
  { code: 'VI', name: 'U.S. Virgin Islands' },
  { code: 'AA', name: 'Armed Forces Americas' },
  { code: 'AE', name: 'Armed Forces Europe / Africa / Middle East' },
  { code: 'AP', name: 'Armed Forces Pacific' },
];

/**
 * Canadian Provinces & Territories for hierarchical lookup preparation.
 */
export const CA_SUBDIVISIONS: SubdivisionItem[] = [
  { code: 'AB', name: 'Alberta' },
  { code: 'BC', name: 'British Columbia' },
  { code: 'MB', name: 'Manitoba' },
  { code: 'NB', name: 'New Brunswick' },
  { code: 'NL', name: 'Newfoundland and Labrador' },
  { code: 'NS', name: 'Nova Scotia' },
  { code: 'ON', name: 'Ontario' },
  { code: 'PE', name: 'Prince Edward Island' },
  { code: 'QC', name: 'Quebec' },
  { code: 'SK', name: 'Saskatchewan' },
  { code: 'NT', name: 'Northwest Territories' },
  { code: 'NU', name: 'Nunavut' },
  { code: 'YT', name: 'Yukon' },
];

/**
 * United Kingdom constituent countries.
 */
export const GB_SUBDIVISIONS: SubdivisionItem[] = [
  { code: 'ENG', name: 'England' },
  { code: 'SCT', name: 'Scotland' },
  { code: 'WLS', name: 'Wales' },
  { code: 'NIR', name: 'Northern Ireland' },
];

/**
 * Major Nigerian States & FCT.
 */
export const NG_SUBDIVISIONS: SubdivisionItem[] = [
  { code: 'AB', name: 'Abia' },
  { code: 'FC', name: 'Abuja (FCT)' },
  { code: 'AD', name: 'Adamawa' },
  { code: 'AK', name: 'Akwa Ibom' },
  { code: 'AN', name: 'Anambra' },
  { code: 'BA', name: 'Bauchi' },
  { code: 'BY', name: 'Bayelsa' },
  { code: 'BE', name: 'Benue' },
  { code: 'BO', name: 'Borno' },
  { code: 'CR', name: 'Cross River' },
  { code: 'DE', name: 'Delta' },
  { code: 'EB', name: 'Ebonyi' },
  { code: 'ED', name: 'Edo' },
  { code: 'EK', name: 'Ekiti' },
  { code: 'EN', name: 'Enugu' },
  { code: 'GO', name: 'Gombe' },
  { code: 'IM', name: 'Imo' },
  { code: 'JI', name: 'Jigawa' },
  { code: 'KD', name: 'Kaduna' },
  { code: 'KN', name: 'Kano' },
  { code: 'KT', name: 'Katsina' },
  { code: 'KE', name: 'Kebbi' },
  { code: 'KO', name: 'Kogi' },
  { code: 'KW', name: 'Kwara' },
  { code: 'LA', name: 'Lagos' },
  { code: 'NA', name: 'Nasarawa' },
  { code: 'NI', name: 'Niger' },
  { code: 'OG', name: 'Ogun' },
  { code: 'ON', name: 'Ondo' },
  { code: 'OS', name: 'Osun' },
  { code: 'OY', name: 'Oyo' },
  { code: 'PL', name: 'Plateau' },
  { code: 'RI', name: 'Rivers' },
  { code: 'SO', name: 'Sokoto' },
  { code: 'TA', name: 'Taraba' },
  { code: 'YO', name: 'Yobe' },
  { code: 'ZA', name: 'Zamfara' },
];

export const SUBDIVISIONS_BY_COUNTRY: Record<string, SubdivisionItem[]> = {
  US: US_SUBDIVISIONS,
  CA: CA_SUBDIVISIONS,
  GB: GB_SUBDIVISIONS,
  NG: NG_SUBDIVISIONS,
};

/**
 * Standard ISO 3166-1 alpha-2 country registry.
 * In accordance with Phase 1 rollout rules, only the United States (US) is enabled.
 */
export const COUNTRIES: CountryItem[] = [
  // Supported country (Phase 1)
  {
    code: 'US',
    name: 'United States of America',
    isSupported: true,
    postalFormatDesc: '5-digit ZIP or ZIP+4 (e.g. 90210 or 90210-1234)',
    postalPlaceholder: '90210 or 90210-1234',
  },
  // Global countries (visible as disabled / coming soon)
  { code: 'CA', name: 'Canada', isSupported: false, postalFormatDesc: 'A1A 1A1', postalPlaceholder: 'K1A 0B1' },
  { code: 'GB', name: 'United Kingdom', isSupported: false, postalFormatDesc: 'Outward/Inward code (e.g. SW1A 1AA)', postalPlaceholder: 'SW1A 1AA' },
  { code: 'NG', name: 'Nigeria', isSupported: false, postalFormatDesc: '6-digit numeric postal code', postalPlaceholder: '102103' },
  { code: 'AU', name: 'Australia', isSupported: false, postalFormatDesc: '4-digit postal code', postalPlaceholder: '2000' },
  { code: 'DE', name: 'Germany', isSupported: false, postalFormatDesc: '5-digit postal code', postalPlaceholder: '10115' },
  { code: 'FR', name: 'France', isSupported: false, postalFormatDesc: '5-digit postal code', postalPlaceholder: '75001' },
  { code: 'JP', name: 'Japan', isSupported: false, postalFormatDesc: '7-digit postal code (e.g. 100-0001)', postalPlaceholder: '100-0001' },
  { code: 'AF', name: 'Afghanistan', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1001' },
  { code: 'AL', name: 'Albania', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1001' },
  { code: 'DZ', name: 'Algeria', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '16000' },
  { code: 'AD', name: 'Andorra', isSupported: false, postalFormatDesc: 'AD + 3 digits', postalPlaceholder: 'AD500' },
  { code: 'AO', name: 'Angola', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '0000' },
  { code: 'AR', name: 'Argentina', isSupported: false, postalFormatDesc: 'Alphanumeric or 4-digit code', postalPlaceholder: 'C1024' },
  { code: 'AM', name: 'Armenia', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '0010' },
  { code: 'AT', name: 'Austria', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1010' },
  { code: 'AZ', name: 'Azerbaijan', isSupported: false, postalFormatDesc: 'AZ + 4 digits', postalPlaceholder: 'AZ1000' },
  { code: 'BS', name: 'Bahamas', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: 'N-4929' },
  { code: 'BH', name: 'Bahrain', isSupported: false, postalFormatDesc: '3 or 4 digits', postalPlaceholder: '317' },
  { code: 'BD', name: 'Bangladesh', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1000' },
  { code: 'BB', name: 'Barbados', isSupported: false, postalFormatDesc: 'BB + 5 digits', postalPlaceholder: 'BB11000' },
  { code: 'BY', name: 'Belarus', isSupported: false, postalFormatDesc: '6-digit code', postalPlaceholder: '220000' },
  { code: 'BE', name: 'Belgium', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1000' },
  { code: 'BZ', name: 'Belize', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '0000' },
  { code: 'BJ', name: 'Benin', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '0000' },
  { code: 'BT', name: 'Bhutan', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '11001' },
  { code: 'BO', name: 'Bolivia', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '0000' },
  { code: 'BA', name: 'Bosnia and Herzegovina', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '71000' },
  { code: 'BW', name: 'Botswana', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '0000' },
  { code: 'BR', name: 'Brazil', isSupported: false, postalFormatDesc: '8-digit code (e.g. 01000-000)', postalPlaceholder: '01001-000' },
  { code: 'BN', name: 'Brunei', isSupported: false, postalFormatDesc: '6-character code', postalPlaceholder: 'BB3713' },
  { code: 'BG', name: 'Bulgaria', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1000' },
  { code: 'BF', name: 'Burkina Faso', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '0000' },
  { code: 'BI', name: 'Burundi', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '0000' },
  { code: 'KH', name: 'Cambodia', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '12000' },
  { code: 'CM', name: 'Cameroon', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '0000' },
  { code: 'CV', name: 'Cape Verde', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '7600' },
  { code: 'CL', name: 'Chile', isSupported: false, postalFormatDesc: '7-digit code', postalPlaceholder: '8320000' },
  { code: 'CN', name: 'China', isSupported: false, postalFormatDesc: '6-digit code', postalPlaceholder: '100000' },
  { code: 'CO', name: 'Colombia', isSupported: false, postalFormatDesc: '6-digit code', postalPlaceholder: '110111' },
  { code: 'CR', name: 'Costa Rica', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '10101' },
  { code: 'HR', name: 'Croatia', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '10000' },
  { code: 'CY', name: 'Cyprus', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1010' },
  { code: 'CZ', name: 'Czech Republic', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '110 00' },
  { code: 'DK', name: 'Denmark', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1000' },
  { code: 'DO', name: 'Dominican Republic', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '10101' },
  { code: 'EC', name: 'Ecuador', isSupported: false, postalFormatDesc: '6-digit code', postalPlaceholder: '170150' },
  { code: 'EG', name: 'Egypt', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '11511' },
  { code: 'EE', name: 'Estonia', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '10115' },
  { code: 'ET', name: 'Ethiopia', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1000' },
  { code: 'FI', name: 'Finland', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '00100' },
  { code: 'GH', name: 'Ghana', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '0000' },
  { code: 'GR', name: 'Greece', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '104 31' },
  { code: 'HK', name: 'Hong Kong', isSupported: false, postalFormatDesc: 'Postal code (999077)', postalPlaceholder: '999077' },
  { code: 'HU', name: 'Hungary', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1011' },
  { code: 'IS', name: 'Iceland', isSupported: false, postalFormatDesc: '3-digit code', postalPlaceholder: '101' },
  { code: 'IN', name: 'India', isSupported: false, postalFormatDesc: '6-digit PIN code', postalPlaceholder: '110001' },
  { code: 'ID', name: 'Indonesia', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '10110' },
  { code: 'IE', name: 'Ireland', isSupported: false, postalFormatDesc: 'Eircode (e.g. D02 X285)', postalPlaceholder: 'D02 X285' },
  { code: 'IL', name: 'Israel', isSupported: false, postalFormatDesc: '7-digit code', postalPlaceholder: '6100000' },
  { code: 'IT', name: 'Italy', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '00118' },
  { code: 'JM', name: 'Jamaica', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '0000' },
  { code: 'JO', name: 'Jordan', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '11118' },
  { code: 'KE', name: 'Kenya', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '00100' },
  { code: 'KR', name: 'South Korea', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '03000' },
  { code: 'KW', name: 'Kuwait', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '13001' },
  { code: 'LV', name: 'Latvia', isSupported: false, postalFormatDesc: 'LV + 4 digits', postalPlaceholder: 'LV-1001' },
  { code: 'LB', name: 'Lebanon', isSupported: false, postalFormatDesc: '8-digit or 4-digit code', postalPlaceholder: '1107 2020' },
  { code: 'LT', name: 'Lithuania', isSupported: false, postalFormatDesc: 'LT + 5 digits', postalPlaceholder: 'LT-01001' },
  { code: 'LU', name: 'Luxembourg', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1111' },
  { code: 'MY', name: 'Malaysia', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '50480' },
  { code: 'MX', name: 'Mexico', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '01000' },
  { code: 'MA', name: 'Morocco', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '10000' },
  { code: 'NL', name: 'Netherlands', isSupported: false, postalFormatDesc: '4 digits + 2 letters (e.g. 1012 AB)', postalPlaceholder: '1012 AB' },
  { code: 'NZ', name: 'New Zealand', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1010' },
  { code: 'NO', name: 'Norway', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '0001' },
  { code: 'PK', name: 'Pakistan', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '44000' },
  { code: 'PA', name: 'Panama', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '0801' },
  { code: 'PE', name: 'Peru', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '15001' },
  { code: 'PH', name: 'Philippines', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '1000' },
  { code: 'PL', name: 'Poland', isSupported: false, postalFormatDesc: '5-digit code (e.g. 00-001)', postalPlaceholder: '00-001' },
  { code: 'PT', name: 'Portugal', isSupported: false, postalFormatDesc: '7-digit code (e.g. 1000-001)', postalPlaceholder: '1000-001' },
  { code: 'QA', name: 'Qatar', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '0000' },
  { code: 'RO', name: 'Romania', isSupported: false, postalFormatDesc: '6-digit code', postalPlaceholder: '010011' },
  { code: 'SA', name: 'Saudi Arabia', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '11564' },
  { code: 'SG', name: 'Singapore', isSupported: false, postalFormatDesc: '6-digit code', postalPlaceholder: '048581' },
  { code: 'ZA', name: 'South Africa', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '2000' },
  { code: 'ES', name: 'Spain', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '28001' },
  { code: 'SE', name: 'Sweden', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '111 22' },
  { code: 'CH', name: 'Switzerland', isSupported: false, postalFormatDesc: '4-digit code', postalPlaceholder: '8001' },
  { code: 'TH', name: 'Thailand', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '10100' },
  { code: 'TR', name: 'Turkey', isSupported: false, postalFormatDesc: '5-digit code', postalPlaceholder: '34000' },
  { code: 'AE', name: 'United Arab Emirates', isSupported: false, postalFormatDesc: 'Postal code', postalPlaceholder: '00000' },
  { code: 'VN', name: 'Vietnam', isSupported: false, postalFormatDesc: '5 or 6 digits', postalPlaceholder: '100000' },
];

/**
 * Postal/ZIP Code Regex specifications per specification requirements:
 * - United States (US): 5-digit ZIP code or ZIP+4 (^\d{5}(-\d{4})?$)
 * - United Kingdom (UK): Alphanumeric outward/inward postal code formatting (^[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}$)
 * - Nigeria (NG): 6-digit standard numeric postal code (^\d{6}$)
 * - Fallback: Standard alphanumeric format (^[a-zA-Z0-9\s-]{3,10}$)
 */
export const POSTAL_REGEX_BY_COUNTRY: Record<string, RegExp> = {
  US: /^\d{5}(-\d{4})?$/,
  GB: /^[A-Za-z]{1,2}\d[A-Za-z\d]?\s*\d[A-Za-z]{2}$/,
  NG: /^\d{6}$/,
};

export const POSTAL_FALLBACK_REGEX = /^[a-zA-Z0-9\s-]{3,10}$/;

/**
 * Resolves country item by ISO code or normalized name.
 */
export function resolveCountry(identifier?: string | null): CountryItem {
  if (!identifier) {
    return COUNTRIES.find((c) => c.code === SUPPORTED_COUNTRY_CODE)!;
  }
  const clean = identifier.trim().toLowerCase();
  const directMatch = COUNTRIES.find(
    (c) => c.code.toLowerCase() === clean || c.name.toLowerCase() === clean,
  );
  if (directMatch) return directMatch;

  // Handle common United States aliases
  const usNames = ['us', 'usa', 'united states', 'united states of america'];
  if (usNames.includes(clean)) {
    return COUNTRIES.find((c) => c.code === SUPPORTED_COUNTRY_CODE)!;
  }

  // Handle common UK aliases
  const ukNames = ['uk', 'united kingdom', 'great britain', 'england'];
  if (ukNames.includes(clean)) {
    const gb = COUNTRIES.find((c) => c.code === 'GB');
    if (gb) return gb;
  }

  return (
    COUNTRIES.find((c) => c.code === SUPPORTED_COUNTRY_CODE) || COUNTRIES[0]
  );
}

/**
 * Returns available subdivisions for country code.
 */
export function getSubdivisionsForCountry(countryCode: string): SubdivisionItem[] {
  return SUBDIVISIONS_BY_COUNTRY[countryCode.toUpperCase()] || [];
}

/**
 * Resolves matching subdivision by name or 2-letter abbreviation code.
 */
export function resolveSubdivision(
  stateValue: string | undefined | null,
  countryCode: string,
): SubdivisionItem | undefined {
  if (!stateValue) return undefined;
  const list = getSubdivisionsForCountry(countryCode);
  const clean = stateValue.trim().toLowerCase();

  return list.find((item) => {
    if (item.code.toLowerCase() === clean) return true;
    if (item.name.toLowerCase() === clean) return true;
    if (`${item.name} (${item.code})`.toLowerCase() === clean) return true;
    return false;
  });
}

/**
 * Dynamic Postal Code Validator per country rules.
 */
export function validatePostalCode(
  rawPostal: string,
  countryCode: string,
): { valid: boolean; formatted: string; error?: string } {
  const code = (countryCode || SUPPORTED_COUNTRY_CODE).toUpperCase();
  const trimmed = (rawPostal || '').trim();

  if (!trimmed) {
    return {
      valid: false,
      formatted: '',
      error: 'Postal code is required.',
    };
  }

  if (code === 'US') {
    const isValid = POSTAL_REGEX_BY_COUNTRY.US.test(trimmed);
    if (!isValid) {
      return {
        valid: false,
        formatted: trimmed,
        error: 'Please enter a valid 5-digit US ZIP code or ZIP+4 (e.g. 90210 or 90210-1234).',
      };
    }
    return { valid: true, formatted: trimmed };
  }

  if (code === 'GB') {
    const isValid = POSTAL_REGEX_BY_COUNTRY.GB.test(trimmed);
    if (!isValid) {
      return {
        valid: false,
        formatted: trimmed,
        error: 'Please enter a valid UK postal code (e.g. SW1A 1AA).',
      };
    }
    // Normalize spacing to single space before inward code
    const normalized = trimmed.toUpperCase().replace(/\s+/, ' ');
    return { valid: true, formatted: normalized };
  }

  if (code === 'NG') {
    const isValid = POSTAL_REGEX_BY_COUNTRY.NG.test(trimmed);
    if (!isValid) {
      return {
        valid: false,
        formatted: trimmed,
        error: 'Please enter a valid 6-digit Nigerian postal code (e.g. 102103).',
      };
    }
    return { valid: true, formatted: trimmed };
  }

  // Fallback for unlisted regions
  const isValid = POSTAL_FALLBACK_REGEX.test(trimmed);
  if (!isValid) {
    return {
      valid: false,
      formatted: trimmed,
      error: 'Please enter a valid postal code (3–10 alphanumeric characters).',
    };
  }

  return { valid: true, formatted: trimmed };
}

/**
 * Splits raw address into Street Address (Line 1) and Unit/Apartment (Line 2).
 */
export function parseAddressLines(rawAddress?: string | null): { street: string; unit: string } {
  if (!rawAddress) return { street: '', unit: '' };
  const cleaned = rawAddress.trim();
  if (cleaned.includes('\n')) {
    const [line1, ...rest] = cleaned.split('\n');
    return { street: line1.trim(), unit: rest.join(' ').trim() };
  }
  // Match comma followed by unit patterns like Apt, Suite, Unit, Ste, Block, Flat, #, etc.
  const unitRegex = /,\s*(Apt|Apartment|Suite|Ste|Unit|Block|Flat|#|Dept|Bldg|Building|Room|Rm)\b/i;
  const match = cleaned.search(unitRegex);
  if (match !== -1) {
    return {
      street: cleaned.slice(0, match).trim(),
      unit: cleaned.slice(match + 1).trim(),
    };
  }
  return { street: cleaned, unit: '' };
}

/**
 * Composes street and unit into single full address string for backend persistence.
 */
export function composeAddress(street: string, unit?: string | null): string {
  const cleanStreet = (street || '').trim();
  const cleanUnit = (unit || '').trim();
  if (!cleanUnit) return cleanStreet;
  return `${cleanStreet}, ${cleanUnit}`;
}

/**
 * Validates primary street address (minimum 5 characters, sanitized).
 */
export function validateStreetAddress(street: string): { valid: boolean; formatted: string; error?: string } {
  const sanitized = (street || '').replace(/[<>]/g, '').trim();
  if (!sanitized) {
    return {
      valid: false,
      formatted: '',
      error: 'Street address is required.',
    };
  }
  if (sanitized.length < 5) {
    return {
      valid: false,
      formatted: sanitized,
      error: 'Street address must be at least 5 characters (e.g., 123 Market Street).',
    };
  }
  return { valid: true, formatted: sanitized };
}

/**
 * Validates optional secondary apartment / unit number (max 30 characters).
 */
export function validateUnit(unit: string): { valid: boolean; formatted: string; error?: string } {
  const sanitized = (unit || '').replace(/[<>]/g, '').trim();
  if (sanitized.length > 30) {
    return {
      valid: false,
      formatted: sanitized.slice(0, 30),
      error: 'Apartment / Block number must be 30 characters or fewer.',
    };
  }
  return { valid: true, formatted: sanitized };
}

/**
 * Validates city name (alphanumeric, spaces, periods, apostrophes, hyphens).
 */
export function validateCity(city: string): { valid: boolean; formatted: string; error?: string } {
  const sanitized = (city || '').trim();
  if (!sanitized) {
    return { valid: false, formatted: '', error: 'City is required.' };
  }
  const cityRegex = /^[a-zA-Z0-9\s.'-]+$/;
  if (!cityRegex.test(sanitized)) {
    return {
      valid: false,
      formatted: sanitized,
      error: 'Please enter a valid city name (letters, numbers, hyphens, and apostrophes).',
    };
  }
  return { valid: true, formatted: sanitized };
}

