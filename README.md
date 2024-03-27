# E-commerce API

## Tech Stack

**Server:** Django, Django rest Framework, HTML

## Run Locally

Clone the project

```bash
  git clone [https://link-to-project](https://github.com/samadaderinto/e-commerce-backend)
```

Go to the project directory

```bash
  cd codematics
```

Install dependencies

```bash
  pip3 install -r requirements.txt
```
or 

```bash
  pip install -r requirements.txt
```

Start the server

```bash
  python3 manage.py runserver 
```

or 

```bash
  python manage.py runserver 
```


## Documentation

[Documentation](https://linktodocumentation)

## Project Structure

```
codematics
├── templates
│   └── email-templates
│      └── (html files)
│
└── media
│    └── images
│       └── (image files)
│
└── codematics
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── asgi.py
│    ├── settings.py
│    ├── urls.py 
│    ├── wsgi.py
│    └── __init__.py
│
└── affiliates
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│    
└──  cart
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└── core
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  payment
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py'
│
└──  product
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  staff
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  store
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  event_notification
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
```
1. assets:
Contains icons and images used in the project.

2. components:
Contains reusable React components.

3. pages:
Contains pages of the application organized by business name.
Each business name directory contains subdirectories for different pages like cart, categories, checkout, home, and wishlist.

4. _app.tsx and _document.tsx:
Next.js specific files for customizing the app and document.

5. _shared:
Contains shared utilities and configurations.

6. favicon.ico:
Favicon icon for the application.

7. globals.css:
Global CSS styles for the application.

8. index.tsx and layout.tsx:
Entry point and layout component for the application.

9. render.tsx:
File for rendering the application theme.

10. shoppesdark, shoppeslight, shoppespurple:
Different theme variations of the application.




## Template Folder Structure

The Template folder structure provided represents the standard organization utilized by various templates within the application. Each template, such as shoppeslight, shoppesdark, or shoppespurple, follows this structured approach for maintaining code consistency and modularity. Below is a brief description of how these folders are utilized within the templates:


```
template
    │   ├── App.tsx
    │   ├── components
    │   ├── configs
    │   ├── features
    │   ├── hooks
    │   ├── layouts
    │   │   ├── footer
    │   │   └── header
    │   ├── libs
    │   ├── pages
    │   │   ├── cart
    │   │   ├── categories
    │   │   │   ├── all
    │   │   │   ├── details
    │   │   │   └── index.tsx
    │   │   ├── checkout
    │   │   ├── home
    │   │   └── wishlist
    │   ├── resourses
    │   │   ├── images
    │   │   │   └── index.tsx
    │   │   ├── index.ts
    │   │   └── svgs
    │   │       └── index.jsx
    │   ├── services
    │   ├── stores
    │   ├── tests
    │   ├── types
    │   └── utils
```

1. App.tsx
This is likely the entry point for the shoppeslight application.

2. components
Contains reusable components used throughout the application.

Components are organized into subdirectories based on their functionality.
Examples include AppAds, ProductBox, SearchInput, SubscribeInputWithButton, and button.

3. configs
Possibly contains configuration files or constants used within the application.

4. features
Contains larger feature components or modules.
Each feature has its own directory and includes relevant components or files.

Examples include AllProducts, BankingAppAdvert, HeroHeader, HomeAndOffice, InvoiceAppAdvert, ProductsDisplay, RecommendedProducts, fashion, and whyChooseUs.

5. hooks
Contains custom React hooks used within the application.

6. layouts
Contains layout-related components such as header and footer.

7. libs
Contains utility functions or libraries used across the application.

8. pages
Contains individual page components for different routes of the application.

Organized into subdirectories based on route categories (e.g., cart, categories, checkout, home, wishlist).

9. resources
Contains image and SVG resources used within the application.

10. services
Contains services or APIs used to interact with backend systems.

11. stores
Contain store configurations or state management related files.

12. tests
Contains tests for the application.

13. types
Contains TypeScript type definitions for various entities such as buttons, headers, product cards, and searches.

14. utils
Contains utility functions or helper files used across the application.


## Routing Folder Structure

- File Routing with Next.js:
Next.js uses a file-based routing system where each file in the pages directory corresponds to a route in the application.
For example, pages/home/index.tsx represents the /home route.

The folder structure under [businessName] contains directories for different pages (cart, categories, checkout, home, wishlist), each with their respective page components.

Each page component may have additional files such as index.tsx for the main content and layout.tsx for the layout structure.

This setup allows for dynamic rendering of different page components based on the selected theme and page name, providing flexibility and modularity in managing templates within the application.

```
── [businessName]
    │   ├── cart
    │   │   ├── index.tsx
    │   │   └── layout.tsx
    │   ├── categories
    │   │   ├── all
    │   │   │   └── index.tsx
    │   │   ├── details
    │   │   │   └── page.tsx
    │   │   └── index.tsx
    │   ├── checkout
    │   │   └── page.tsx
    │   ├── home
    │   │   ├── index.tsx
    │   │   └── layout.tsx
    │   ├── layout.tsx
    │   ├── page.tsx
    │   └── wishlist
    │       └── page.tsx
```

- Render Function:

``` bash
 <Render pageName={pageName} templateName="shoppeslight" />
```

The Render component is responsible for rendering the appropriate page component based on the selected theme and page name.

It receives pageName and templateName as props.
It retrieves the appropriate component from the componentMap based on the provided templateName and pageName.

If the specified template or page is not found in the componentMap, it defaults to rendering the Not found component.

- Component Mapping:

``` bash
const componentMap: { [key: string]: { [key: string]: React.ComponentType<any> } } = {
    shoppesdark: {
        Cart: CartDark,
        Checkout: CheckoutDark,
        Home: HomeDark,
        Wishlist: WishlistDark,
        AllCategory: AllCategoryDark,
        CategoryDetails: CategoryDetailsDark,
    },
    shoppeslight: {
        Cart: CartLight,
        Checkout: CheckoutLight,
        Home: HomeLight,
        Wishlist: WishlistLight,
        AllCategory: AllCategoryLight,
        CategoryDetails: CategoryDetailsLight,
        CategoriesLight: CategoriesLight
    },
    shoppespurple: {
        Cart: CartPurple,
        Checkout: CheckoutPurple,
        Home: HomePurple,
        Wishlist: WishlistPurple,
        AllCategory: AllCategoryPurple,
        CategoryDetails: CategoryDetailsPurple,
    },
};
```
componentMap is an object that maps template names to their corresponding page components.

Each template object within componentMap contains mappings from page names to their respective components.

For example, shoppeslight template maps page names like Cart, Checkout, Home, etc., to their respective components like CartLight, CheckoutLight, HomeLight, etc.

Usage Example:
In the provided example, the Home component imports the Render component.

It specifies the pageName as 'Home' and templateName as 'shoppeslight'.

The Render component then renders the HomeLight component based on the provided page and template names.
