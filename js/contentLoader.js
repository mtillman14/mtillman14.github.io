export default class ContentLoader {
    constructor() {
        this.contentCache = new Map();
    }

    async loadContent(page) {
        try {
            // Show loading state
            const contentArea = document.getElementById('content-area');
            contentArea.innerHTML = '<div class="loading">Loading...</div>';

            // Check cache first
            if (this.contentCache.has(page)) {
                contentArea.innerHTML = this.contentCache.get(page);
                return;
            }

            const response = await fetch(`content/${page}.html`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            let content = await response.text();

            // Extract just the body content, excluding head and html tags
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = content;
            
            // Get everything after the head tag and before the html closing tag
            const bodyContent = Array.from(tempDiv.children)
                .filter(el => !['head', 'html'].includes(el.tagName.toLowerCase()))
                .map(el => el.outerHTML)
                .join('');

            // Cache the content
            this.contentCache.set(page, bodyContent);

            // Update the content area
            contentArea.innerHTML = bodyContent;

            // Update the URL without page reload
            history.pushState({page: page}, '', `#${page}`);
        } catch (error) {
            console.error('Error loading content:', error);
            document.getElementById('content-area').innerHTML = 
                '<div class="error">Error loading content. Please try again.</div>';
        }
    }
}