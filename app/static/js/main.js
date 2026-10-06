document.addEventListener('DOMContentLoaded', function () {
    const buttons = document.querySelectorAll('[data-add-to-cart]');
    buttons.forEach(function (button) {
        button.addEventListener('click', function () {
            const form = button.closest('form');
            if (form) {
                form.submit();
            }
        });
    });

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const defaults = { delay: 60, duration: 300, maxTotal: 800, maxStagger: 10 };
    const positions = new WeakMap();

    function playEntrance(item, direction, delay, duration) {
        const offsets = {
            down: ['0px', '16px', '1'],
            up: ['0px', '-16px', '1'],
            right: ['-16px', '0px', '1'],
            scale: ['0px', '0px', '0.9']
        };
        const [x, y, scale] = offsets[direction] || offsets.up;

        item.classList.remove('stagger-pending');
        item.style.willChange = 'transform, opacity';
        const animation = item.animate([
            { opacity: 0, transform: `translate3d(${x}, ${y}, 0) scale(${scale})` },
            { opacity: 1, transform: 'translate3d(0, 0, 0) scale(1)' }
        ], {
            duration: duration,
            delay: delay,
            easing: 'cubic-bezier(0.25, 0.1, 0.25, 1)',
            fill: 'both'
        });

        animation.onfinish = function () {
            item.classList.remove('stagger-pending');
            item.style.willChange = '';
            animation.cancel();
        };
    }

    function staggerBatch(items, container) {
        if (!items.length) return;
        const delay = Number(container.dataset.staggerDelay) || defaults.delay;
        const duration = Number(container.dataset.staggerDuration) || defaults.duration;
        const maxStagger = Number(container.dataset.staggerMax) || defaults.maxStagger;
        const maxTotal = Number(container.dataset.staggerTotal) || defaults.maxTotal;
        const isGrid = container.dataset.stagger === 'grid';
        const columns = isGrid
            ? Math.max(1, getComputedStyle(container).gridTemplateColumns.split(' ').length)
            : 1;
        const count = Math.min(items.length, maxStagger);
        const maxStep = count > 1
            ? Math.max(...items.slice(0, count).map(function (_, index) {
                return isGrid ? Math.floor(index / columns) + (index % columns) : index;
            }))
            : 0;
        const safeDelay = maxStep
            ? Math.min(delay, Math.max(0, maxTotal - duration) / maxStep)
            : 0;

        items.forEach(function (item, index) {
            const step = isGrid
                ? Math.floor(index / columns) + (index % columns)
                : index;
            const itemDelay = index < maxStagger ? step * safeDelay : 0;
            playEntrance(item, container.dataset.staggerDirection || 'up', itemDelay, duration);
        });
    }

    function capturePositions(container) {
        Array.from(container.children).forEach(function (item) {
            positions.set(item, item.getBoundingClientRect());
        });
    }

    function animateLayoutChanges(container) {
        Array.from(container.children).forEach(function (item) {
            const previous = positions.get(item);
            const current = item.getBoundingClientRect();
            positions.set(item, current);

            if (!previous || item.classList.contains('stagger-pending')) return;
            const deltaX = previous.left - current.left;
            const deltaY = previous.top - current.top;
            if (!deltaX && !deltaY) return;

            item.style.willChange = 'transform';
            const animation = item.animate([
                { transform: `translate3d(${deltaX}px, ${deltaY}px, 0)` },
                { transform: 'translate3d(0, 0, 0)' }
            ], { duration: 300, easing: 'cubic-bezier(0.25, 0.1, 0.25, 1)' });
            animation.onfinish = function () {
                item.style.willChange = '';
                animation.cancel();
            };
        });
    }

    (function initializeStaggerReveal() {
    if (reducedMotion) return;

    const containers = document.querySelectorAll('[data-stagger]');
    if (!containers.length) return;

    if (!('IntersectionObserver' in window)) {
        containers.forEach(function (container) {
            staggerBatch(Array.from(container.children), container);
        });
        return;
    }

    const visibleItems = new Map();
    const itemObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (!entry.isIntersecting) return;
            itemObserver.unobserve(entry.target);
            const container = entry.target.parentElement;
            if (!visibleItems.has(container)) visibleItems.set(container, []);
            visibleItems.get(container).push(entry.target);
        });

        visibleItems.forEach(function (items, container) {
            staggerBatch(items, container);
        });
        visibleItems.clear();
    }, { threshold: 0.12 });

    containers.forEach(function (container) {
        function observeNewItems(items) {
            const mountItems = [];
            items.forEach(function (item) {
                if (item.nodeType !== 1 || item.dataset.staggerObserved) return;
                item.dataset.staggerObserved = 'true';
                item.classList.add('stagger-pending');
                positions.set(item, item.getBoundingClientRect());

                if (container.dataset.staggerTrigger === 'mount') {
                    mountItems.push(item);
                } else {
                    itemObserver.observe(item);
                }
            });
            if (mountItems.length) staggerBatch(mountItems, container);
        }

        observeNewItems(Array.from(container.children));
        capturePositions(container);

        const mutationObserver = new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                observeNewItems(Array.from(mutation.addedNodes));
            });
            requestAnimationFrame(function () { animateLayoutChanges(container); });
        });
        mutationObserver.observe(container, { childList: true });
    });

    window.StaggerReveal = {
        remove: function (item, removeCallback) {
            if (reducedMotion) {
                if (removeCallback) removeCallback();
                else item.remove();
                return;
            }

            item.style.willChange = 'transform, opacity';
            const animation = item.animate([
                { opacity: 1, transform: 'scale(1)' },
                { opacity: 0, transform: 'scale(0.95)' }
            ], { duration: 180, easing: 'cubic-bezier(0.25, 0.1, 0.25, 1)' });
            animation.onfinish = function () {
                item.style.willChange = '';
                if (removeCallback) removeCallback();
                else item.remove();
                animation.cancel();
            };
        }
    };
    })();

    const accountApp = document.querySelector('[data-account-app]');
    if (accountApp) {
        const sidebar = accountApp.querySelector('.dashboard-sidebar');
        const collapseButton = accountApp.querySelector('[data-sidebar-collapse]');
        const openButton = accountApp.querySelector('[data-sidebar-open]');
        const backdrop = accountApp.querySelector('[data-sidebar-backdrop]');
        const compactSidebar = window.matchMedia('(max-width: 1024px)');

        function syncSidebar() {
            if (compactSidebar.matches) accountApp.classList.add('is-collapsed');
            else accountApp.classList.toggle('is-collapsed', localStorage.getItem('account-sidebar-collapsed') === 'true');
        }
        syncSidebar();
        compactSidebar.addEventListener('change', syncSidebar);
        collapseButton.addEventListener('click', function () {
            const collapsed = !accountApp.classList.contains('is-collapsed');
            accountApp.classList.toggle('is-collapsed', collapsed);
            localStorage.setItem('account-sidebar-collapsed', String(collapsed));
            collapseButton.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
        });

        function closeDrawer() { accountApp.classList.remove('drawer-open'); }
        openButton.addEventListener('click', function () { accountApp.classList.add('drawer-open'); });
        backdrop.addEventListener('click', closeDrawer);
        sidebar.querySelectorAll('a').forEach(function (link) { link.addEventListener('click', closeDrawer); });
        document.addEventListener('keydown', function (event) { if (event.key === 'Escape') closeDrawer(); });

        const searchDetails = accountApp.querySelector('.topbar-search');
        let searchBackdrop;
        searchDetails.addEventListener('toggle', function () {
            if (searchDetails.open) {
                searchBackdrop = document.createElement('button');
                searchBackdrop.type = 'button';
                searchBackdrop.className = 'search-backdrop';
                searchBackdrop.setAttribute('aria-label', 'Close search');
                searchBackdrop.addEventListener('click', function () { searchDetails.open = false; });
                document.body.appendChild(searchBackdrop);
                searchDetails.querySelector('input').focus();
            } else if (searchBackdrop) {
                searchBackdrop.remove();
                searchBackdrop = null;
            }
        });
    }

    document.querySelectorAll('[data-password-toggle]').forEach(function (toggle) {
        toggle.addEventListener('click', function () {
            const input = toggle.closest('.password-control').querySelector('[data-password-input]');
            const show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            toggle.textContent = show ? 'Hide' : 'Show';
            toggle.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
            input.focus();
        });
    });

    document.querySelectorAll('[data-auth-form]').forEach(function (form) {
        form.addEventListener('submit', function () {
            if (form.matches('[data-validate-form]') || !form.checkValidity()) return;
            const button = form.querySelector('.auth-submit');
            button.disabled = true;
            button.classList.add('is-loading');
        });
    });

    const settingsForm = document.querySelector('[data-settings-form]');
    if (settingsForm) {
        const saveBar = document.querySelector('[data-save-bar]');
        const saveStatus = document.querySelector('[data-save-status]');
        let saveTimer;

        async function saveSettings() {
            window.clearTimeout(saveTimer);
            saveStatus.textContent = 'Saving…';
            saveStatus.classList.add('is-saving');
            try {
                const response = await fetch(settingsForm.action || window.location.href, {
                    method: 'POST',
                    body: new FormData(settingsForm),
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                if (!response.ok) throw new Error('Save failed');
                saveStatus.textContent = 'Saved';
                saveStatus.classList.remove('is-saving', 'is-error');
                saveBar.hidden = true;
            } catch (error) {
                saveStatus.textContent = 'Could not save. Try again.';
                saveStatus.classList.remove('is-saving');
                saveStatus.classList.add('is-error');
                saveBar.hidden = false;
            }
        }

        settingsForm.addEventListener('change', function () {
            saveBar.hidden = false;
            saveStatus.textContent = 'Unsaved changes';
            saveStatus.classList.remove('is-error');
            window.clearTimeout(saveTimer);
            saveTimer = window.setTimeout(saveSettings, 1500);
        });
        settingsForm.addEventListener('submit', function (event) {
            event.preventDefault();
            saveSettings();
        });
        document.querySelector('[data-discard-settings]').addEventListener('click', function () {
            window.clearTimeout(saveTimer);
            settingsForm.reset();
            saveBar.hidden = true;
            saveStatus.textContent = 'Changes discarded';
        });
    }

    const deleteDialog = document.querySelector('[data-delete-dialog]');
    if (deleteDialog) {
        document.querySelector('[data-delete-account]').addEventListener('click', function () { deleteDialog.showModal(); });
        document.querySelector('[data-close-delete]').addEventListener('click', function () { deleteDialog.close(); });
    }

    const shareButton = document.querySelector('[data-share-profile]');
    if (shareButton) {
        shareButton.addEventListener('click', async function () {
            try {
                if (navigator.share) await navigator.share({ title: document.title, url: window.location.href });
                else { await navigator.clipboard.writeText(window.location.href); shareButton.textContent = 'Copied'; }
            } catch (error) {
                shareButton.textContent = 'Link ready';
            }
        });
    }

    const storefrontMenu = document.querySelector('[data-storefront-menu]');
    const storefrontNav = document.querySelector('#storefront-navigation');
    const storefrontBackdrop = document.querySelector('[data-storefront-menu-close]');
    if (storefrontMenu && storefrontNav && storefrontBackdrop) {
        function closeStorefrontMenu(returnFocus) {
            document.body.classList.remove('storefront-menu-open');
            storefrontMenu.setAttribute('aria-expanded', 'false');
            storefrontMenu.setAttribute('aria-label', 'Open navigation');
            if (returnFocus) storefrontMenu.focus();
        }

        storefrontMenu.addEventListener('click', function () {
            const isOpen = document.body.classList.toggle('storefront-menu-open');
            storefrontMenu.setAttribute('aria-expanded', String(isOpen));
            storefrontMenu.setAttribute('aria-label', isOpen ? 'Close navigation' : 'Open navigation');
            if (isOpen) storefrontNav.querySelector('a').focus();
        });
        storefrontBackdrop.addEventListener('click', function () { closeStorefrontMenu(true); });
        storefrontNav.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () { closeStorefrontMenu(false); });
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeStorefrontMenu(true);
                storefrontNav.querySelectorAll('details[open]').forEach(function (menu) { menu.open = false; });
            }
            if (event.key === 'Tab' && document.body.classList.contains('storefront-menu-open')) {
                const focusable = Array.from(storefrontNav.querySelectorAll('a, summary, button')).filter(function (item) {
                    return !item.hidden && item.getClientRects().length;
                });
                const first = focusable[0];
                const last = focusable[focusable.length - 1];
                if (event.shiftKey && document.activeElement === first) {
                    event.preventDefault();
                    last.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                    event.preventDefault();
                    first.focus();
                }
            }
        });
        document.addEventListener('click', function (event) {
            storefrontNav.querySelectorAll('details[open]').forEach(function (menu) {
                if (!menu.contains(event.target)) menu.open = false;
            });
        });
    }

    const filterDrawer = document.querySelector('.catalog-filters');
    if (filterDrawer) {
        const openFilter = document.querySelector('[data-filter-open]');
        const closeFilters = document.querySelectorAll('[data-filter-close]');
        openFilter.addEventListener('click', function () { document.body.classList.add('filters-open'); });
        closeFilters.forEach(function (button) {
            button.addEventListener('click', function () { document.body.classList.remove('filters-open'); });
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') document.body.classList.remove('filters-open');
        });
    }

    document.querySelectorAll('[data-price-slider]').forEach(function (slider) {
        const minRange = slider.querySelector('[data-min-range]');
        const maxRange = slider.querySelector('[data-max-range]');
        const minDisplay = slider.parentElement.querySelector('[data-min-display]');
        const maxDisplay = slider.parentElement.querySelector('[data-max-display]');
        const fill = slider.querySelector('[data-range-fill]');
        const absoluteMin = Number(slider.dataset.min);
        const absoluteMax = Number(slider.dataset.max);

        function syncPriceControls(changed) {
            let minValue = Number(minRange.value);
            let maxValue = Number(maxRange.value);
            if (minValue > maxValue) {
                if (changed === minRange) minValue = maxValue;
                else maxValue = minValue;
            }
            minRange.value = minValue;
            maxRange.value = maxValue;
            minDisplay.value = minValue;
            maxDisplay.value = maxValue;
            const span = Math.max(1, absoluteMax - absoluteMin);
            fill.style.left = `${((minValue - absoluteMin) / span) * 100}%`;
            fill.style.right = `${100 - ((maxValue - absoluteMin) / span) * 100}%`;
        }

        minRange.addEventListener('input', function () { syncPriceControls(minRange); });
        maxRange.addEventListener('input', function () { syncPriceControls(maxRange); });
        [minRange, maxRange].forEach(function (range) {
            range.addEventListener('change', function () { document.querySelector('#catalog-filters-form').requestSubmit(); });
        });
        minDisplay.addEventListener('change', function () {
            minRange.value = Math.min(Number(minDisplay.value), absoluteMax);
            syncPriceControls(minRange);
            document.querySelector('#catalog-filters-form').requestSubmit();
        });
        maxDisplay.addEventListener('change', function () {
            maxRange.value = Math.max(Number(maxDisplay.value), absoluteMin);
            syncPriceControls(maxRange);
            document.querySelector('#catalog-filters-form').requestSubmit();
        });
        syncPriceControls();
    });

    document.querySelectorAll('[data-auto-submit]').forEach(function (control) {
        control.addEventListener('change', function () { control.form.requestSubmit(); });
    });

    document.querySelectorAll('[data-quantity-change]').forEach(function (button) {
        button.addEventListener('click', function () {
            const input = button.parentElement.querySelector('input[name="quantity"]');
            const min = Number(input.min) || 1;
            const max = Number(input.max) || 99;
            input.value = Math.min(max, Math.max(min, Number(input.value) + Number(button.dataset.quantityChange)));
        });
    });

    const lightbox = document.querySelector('[data-product-lightbox]');
    if (lightbox) {
        document.querySelector('[data-open-lightbox]').addEventListener('click', function () { lightbox.showModal(); });
        document.querySelector('[data-close-lightbox]').addEventListener('click', function () { lightbox.close(); });
        lightbox.addEventListener('click', function (event) { if (event.target === lightbox) lightbox.close(); });
    }

    const productTabs = document.querySelector('[data-product-tabs]');
    if (productTabs) {
        const tabs = productTabs.querySelectorAll('[data-product-tab]');
        const activateTab = function (name) {
            tabs.forEach(function (tab) {
                const selected = tab.dataset.productTab === name;
                tab.setAttribute('aria-selected', String(selected));
                productTabs.querySelector(`[data-product-panel="${tab.dataset.productTab}"]`).hidden = !selected;
            });
        };
        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () { activateTab(tab.dataset.productTab); });
        });
        if (window.location.hash === '#reviews') activateTab('reviews');
    }

    document.querySelectorAll('[data-checkout-total]').forEach(function (amount) {
        const form = amount.closest('.checkout-grid')?.querySelector('#checkout-form');
        if (!form) return;
        const standard = Number(form.dataset.standardShipping || 0);
        const express = Number(form.dataset.expressShipping || 0);
        const subtotal = Number(form.dataset.subtotal || 0);
        const summaryRows = Array.from(amount.closest('.checkout-grid').querySelectorAll('.checkout-summary .summary-row'));
        const shippingRow = summaryRows.find(function (row) { return row.textContent.toLowerCase().includes('delivery'); });
        form.querySelectorAll('input[name="shipping"]').forEach(function (radio) {
            radio.addEventListener('change', function () {
                const shippingAmount = radio.value === 'express' ? express : standard;
                amount.textContent = (subtotal + shippingAmount).toFixed(2);
                if (shippingRow) {
                    shippingRow.querySelector('span').textContent = radio.value === 'express' ? 'Express delivery' : 'Standard delivery';
                    shippingRow.querySelector('strong').textContent = shippingAmount === 0 ? 'Free' : `₹${shippingAmount.toFixed(2)}`;
                }
            });
        });
    });

    const adminApp = document.querySelector('.admin-app');
    if (adminApp) {
        const adminTopbar = adminApp.querySelector('.admin-topbar');
        const adminSidebar = adminApp.querySelector('.admin-sidebar');
        const menuButton = document.createElement('button');
        menuButton.type = 'button';
        menuButton.className = 'admin-menu-toggle';
        menuButton.setAttribute('aria-label', 'Open admin navigation');
        menuButton.textContent = '☰';
        const adminBackdrop = document.createElement('button');
        adminBackdrop.type = 'button';
        adminBackdrop.className = 'admin-sidebar-backdrop';
        adminBackdrop.setAttribute('aria-label', 'Close admin navigation');
        adminTopbar.prepend(menuButton);
        adminApp.appendChild(adminBackdrop);

        function closeAdminMenu() {
            adminApp.classList.remove('menu-open');
            menuButton.setAttribute('aria-label', 'Open admin navigation');
        }
        menuButton.addEventListener('click', function () {
            const isOpen = adminApp.classList.toggle('menu-open');
            menuButton.setAttribute('aria-label', isOpen ? 'Close admin navigation' : 'Open admin navigation');
        });
        adminBackdrop.addEventListener('click', closeAdminMenu);
        adminSidebar.querySelectorAll('a').forEach(function (link) { link.addEventListener('click', closeAdminMenu); });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') closeAdminMenu();
        });

        let goPrefix = false;
        document.addEventListener('keydown', function (event) {
            if (event.target.matches('input, textarea, select, [contenteditable="true"]')) return;
            if (event.key.toLowerCase() === 'g') {
                goPrefix = true;
                window.setTimeout(function () { goPrefix = false; }, 900);
                return;
            }
            if (!goPrefix) return;
            goPrefix = false;
            const destinations = { d: '/admin', u: '/admin/users', a: '/admin/analytics', l: '/admin/audit' };
            if (destinations[event.key.toLowerCase()]) window.location.href = destinations[event.key.toLowerCase()];
        });
    }

    const commandPalette = document.querySelector('[data-command-palette]');
    if (commandPalette) {
        const commandSearch = commandPalette.querySelector('[data-command-search]');
        const commandLinks = Array.from(commandPalette.querySelectorAll('nav a'));
        document.addEventListener('keydown', function (event) {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
                event.preventDefault();
                commandPalette.showModal();
                commandSearch.focus();
            }
        });
        commandSearch.addEventListener('input', function () {
            const term = commandSearch.value.trim().toLowerCase();
            commandLinks.forEach(function (link) {
                link.hidden = !link.textContent.toLowerCase().includes(term);
            });
        });
    }

    let globalPalette = document.querySelector('[data-global-command]');
    if (!globalPalette && !document.body.classList.contains('admin-page')) {
        globalPalette = document.createElement('dialog');
        globalPalette.className = 'command-palette storefront-command-palette';
        globalPalette.id = 'global-search-palette';
        globalPalette.setAttribute('aria-label', 'Global search and commands');
        globalPalette.innerHTML = '<form class="global-command-search" data-global-form><span aria-hidden="true">⌕</span><input type="search" placeholder="Search products, orders, or pages…" aria-label="Search products, orders, or pages" data-global-search autocomplete="off"><button type="button" data-clear-global-search aria-label="Clear search">×</button><kbd>ESC</kbd></form><div class="global-command-recent" data-global-recent></div><div class="global-command-results" data-global-results role="listbox" aria-label="Search results"></div><p class="global-command-empty" data-global-empty hidden>No matches found. Try another search.</p><footer><span>↑↓ to navigate</span><span>Enter to open</span><span>ESC to close</span></footer>';
        document.body.appendChild(globalPalette);
    }

    if (globalPalette) {
        const globalInput = globalPalette.querySelector('[data-global-search]');
        const globalResults = globalPalette.querySelector('[data-global-results]');
        const globalRecent = globalPalette.querySelector('[data-global-recent]');
        const globalEmpty = globalPalette.querySelector('[data-global-empty]');
        const openButtons = Array.from(document.querySelectorAll('[data-command-open]'));
        let resultItems = [];
        let activeResult = -1;
        let searchTimer;
        let searchController;

        function recentSearches() {
            try { return JSON.parse(localStorage.getItem('sweet-shop-recent-searches') || '[]').slice(0, 5); }
            catch (error) { return []; }
        }

        function rememberSearch(term) {
            const normalized = term.trim();
            if (!normalized) return;
            const recents = recentSearches().filter(function (item) { return item.toLowerCase() !== normalized.toLowerCase(); });
            recents.unshift(normalized);
            localStorage.setItem('sweet-shop-recent-searches', JSON.stringify(recents.slice(0, 5)));
        }

        function highlightText(element, text, term) {
            const lowerText = text.toLowerCase();
            const lowerTerm = term.toLowerCase();
            const matchIndex = lowerTerm ? lowerText.indexOf(lowerTerm) : -1;
            if (matchIndex < 0) {
                element.textContent = text;
                return;
            }
            element.append(document.createTextNode(text.slice(0, matchIndex)));
            const mark = document.createElement('mark');
            mark.textContent = text.slice(matchIndex, matchIndex + term.length);
            element.append(mark, document.createTextNode(text.slice(matchIndex + term.length)));
        }

        function renderRecentSearches() {
            globalRecent.replaceChildren();
            const recents = recentSearches();
            if (!recents.length) return;
            const heading = document.createElement('p');
            heading.className = 'global-command-heading';
            heading.textContent = 'Recent searches';
            globalRecent.appendChild(heading);
            recents.forEach(function (term) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'global-recent-search';
                button.textContent = `◷  ${term}`;
                button.addEventListener('click', function () {
                    globalInput.value = term;
                    runGlobalSearch(term);
                    globalInput.focus();
                });
                globalRecent.appendChild(button);
            });
        }

        function renderGlobalResults(groups, term) {
            globalResults.replaceChildren();
            resultItems = [];
            activeResult = -1;
            (groups || []).forEach(function (group) {
                if (!group.items || !group.items.length) return;
                const heading = document.createElement('p');
                heading.className = 'global-command-heading';
                heading.textContent = group.label;
                globalResults.appendChild(heading);
                group.items.forEach(function (item) {
                    const option = document.createElement('a');
                    option.href = item.href;
                    option.className = 'global-command-option';
                    option.setAttribute('role', 'option');
                    option.setAttribute('aria-selected', 'false');
                    option.dataset.resultTitle = item.title;
                    const icon = document.createElement('span');
                    icon.className = 'global-result-icon';
                    icon.setAttribute('aria-hidden', 'true');
                    icon.textContent = item.icon || '↗';
                    const copy = document.createElement('span');
                    copy.className = 'global-result-copy';
                    const title = document.createElement('strong');
                    highlightText(title, item.title, term);
                    const detail = document.createElement('small');
                    detail.textContent = item.detail || '';
                    copy.append(title, detail);
                    option.append(icon, copy);
                    option.addEventListener('click', function () {
                        rememberSearch(globalInput.value);
                        globalPalette.close();
                    });
                    globalResults.appendChild(option);
                    resultItems.push(option);
                });
            });
            globalEmpty.hidden = resultItems.length > 0;
        }

        async function runGlobalSearch(term) {
            window.clearTimeout(searchTimer);
            if (searchController) searchController.abort();
            searchController = new AbortController();
            globalPalette.classList.toggle('is-searching', Boolean(term));
            try {
                const response = await fetch(`/api/search?q=${encodeURIComponent(term)}`, { signal: searchController.signal });
                if (!response.ok) throw new Error('Search failed');
                const data = await response.json();
                if (globalInput.value.trim() !== term) return;
                renderGlobalResults(data.groups, term);
                renderRecentSearches();
            } catch (error) {
                if (error.name !== 'AbortError') {
                    globalResults.replaceChildren();
                    globalEmpty.textContent = 'Search is unavailable right now. Try the shop page instead.';
                    globalEmpty.hidden = false;
                }
            } finally {
                globalPalette.classList.remove('is-searching');
            }
        }

        function openGlobalPalette() {
            if (!globalPalette.open) globalPalette.showModal();
            openButtons.forEach(function (button) { button.setAttribute('aria-expanded', 'true'); });
            renderRecentSearches();
            globalInput.value = '';
            runGlobalSearch('');
            globalInput.focus();
        }

        openButtons.forEach(function (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                openGlobalPalette();
            });
        });
        document.addEventListener('keydown', function (event) {
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
                event.preventDefault();
                openGlobalPalette();
                return;
            }
            if (!globalPalette.open || !resultItems.length) return;
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                const direction = event.key === 'ArrowDown' ? 1 : -1;
                activeResult = (activeResult + direction + resultItems.length) % resultItems.length;
                resultItems.forEach(function (item, index) {
                    const active = index === activeResult;
                    item.setAttribute('aria-selected', String(active));
                    if (active) item.scrollIntoView({ block: 'nearest' });
                });
            } else if (event.key === 'Enter' && activeResult >= 0) {
                event.preventDefault();
                resultItems[activeResult].click();
            }
        });
        globalInput.addEventListener('input', function () {
            const term = globalInput.value.trim();
            globalEmpty.textContent = 'No matches found. Try another search.';
            searchTimer = window.setTimeout(function () { runGlobalSearch(term); }, 240);
        });
        globalPalette.querySelector('[data-clear-global-search]').addEventListener('click', function () {
            globalInput.value = '';
            runGlobalSearch('');
            globalInput.focus();
        });
        globalPalette.querySelector('[data-global-form]').addEventListener('submit', function (event) { event.preventDefault(); });
        globalPalette.addEventListener('close', function () {
            openButtons.forEach(function (button) { button.setAttribute('aria-expanded', 'false'); });
            if (searchController) searchController.abort();
        });
        globalPalette.addEventListener('click', function (event) {
            if (event.target === globalPalette) globalPalette.close();
        });
    }

    const addUserDialog = document.querySelector('[data-add-user-dialog]');
    if (addUserDialog) {
        document.querySelector('[data-open-add-user]').addEventListener('click', function () { addUserDialog.showModal(); });
        document.querySelector('[data-close-add-user]').addEventListener('click', function () { addUserDialog.close(); });
    }

    const bulkUserForm = document.querySelector('#bulk-user-action');
    if (bulkUserForm) {
        const selectAll = document.querySelector('[data-select-all]');
        const selections = Array.from(document.querySelectorAll('[data-user-select]'));
        const selectedCount = document.querySelector('[data-selected-count]');
        const deleteDialog = document.querySelector('[data-bulk-delete-dialog]');

        function updateSelection() {
            const selected = selections.filter(function (checkbox) { return checkbox.checked; }).length;
            selectedCount.textContent = `${selected} selected`;
            selectAll.checked = selected > 0 && selected === selections.length;
            selectAll.indeterminate = selected > 0 && selected < selections.length;
        }

        selectAll.addEventListener('change', function () {
            selections.forEach(function (checkbox) { checkbox.checked = selectAll.checked; });
            updateSelection();
        });
        selections.forEach(function (checkbox) { checkbox.addEventListener('change', updateSelection); });
        bulkUserForm.addEventListener('submit', function (event) {
            const action = bulkUserForm.elements.action.value;
            if (!selections.some(function (checkbox) { return checkbox.checked; })) {
                event.preventDefault();
                selectedCount.textContent = 'Select at least one account';
            } else if (action === 'delete' && bulkUserForm.dataset.deleteConfirmed !== 'true') {
                event.preventDefault();
                deleteDialog.showModal();
            }
        });
        document.querySelector('[data-confirm-bulk-delete]').addEventListener('click', function (event) {
            event.preventDefault();
            bulkUserForm.dataset.deleteConfirmed = 'true';
            deleteDialog.close();
            bulkUserForm.requestSubmit();
        });
        updateSelection();

        document.querySelectorAll('.inline-access-form select').forEach(function (select) {
            select.addEventListener('change', function () { select.form.requestSubmit(); });
        });
    }

    document.querySelectorAll('.admin-tools-shortcut').forEach(function (shortcut) {
        shortcut.addEventListener('click', function () { window.location.href = shortcut.href; });
    });

    document.querySelectorAll('[data-testimonial-carousel]').forEach(function (carousel) {
        const slides = Array.from(carousel.querySelectorAll('[data-testimonial-slide]'));
        const dots = Array.from(carousel.querySelectorAll('[data-testimonial-dot]'));
        const previous = carousel.querySelector('[data-testimonial-prev]');
        const next = carousel.querySelector('[data-testimonial-next]');
        let activeIndex = 0;
        let touchStart = 0;

        function showSlide(index) {
            activeIndex = (index + slides.length) % slides.length;
            slides.forEach(function (slide, slideIndex) {
                const active = slideIndex === activeIndex;
                slide.hidden = !active;
                slide.classList.toggle('is-current', active);
            });
            dots.forEach(function (dot, dotIndex) {
                if (dotIndex === activeIndex) dot.setAttribute('aria-current', 'true');
                else dot.removeAttribute('aria-current');
            });
        }

        previous.addEventListener('click', function () { showSlide(activeIndex - 1); });
        next.addEventListener('click', function () { showSlide(activeIndex + 1); });
        dots.forEach(function (dot) {
            dot.addEventListener('click', function () { showSlide(Number(dot.dataset.testimonialDot)); });
        });
        carousel.addEventListener('keydown', function (event) {
            if (event.key === 'ArrowLeft') showSlide(activeIndex - 1);
            if (event.key === 'ArrowRight') showSlide(activeIndex + 1);
        });
        carousel.addEventListener('touchstart', function (event) { touchStart = event.changedTouches[0].screenX; }, { passive: true });
        carousel.addEventListener('touchend', function (event) {
            const delta = event.changedTouches[0].screenX - touchStart;
            if (Math.abs(delta) > 45) showSlide(activeIndex + (delta < 0 ? 1 : -1));
        }, { passive: true });
    });

    document.querySelectorAll('[data-toast]').forEach(function (toast) {
        let dismissTimer;
        const toastText = toast.textContent.toLowerCase();
        if (/success|saved|added|removed|applied|updated|on the list|created|placed/.test(toastText)) {
            toast.classList.add('toast-success');
        } else if (/invalid|error|could not|not valid|failed|choose|enter a valid/.test(toastText)) {
            toast.classList.add('toast-error');
            toast.setAttribute('role', 'alert');
        }
        function dismissToast() {
            window.clearTimeout(dismissTimer);
            toast.classList.add('is-dismissing');
            window.setTimeout(function () { toast.remove(); }, reducedMotion ? 0 : 180);
        }
        function scheduleDismiss() { dismissTimer = window.setTimeout(dismissToast, 5500); }
        toast.addEventListener('mouseenter', function () { window.clearTimeout(dismissTimer); });
        toast.addEventListener('mouseleave', scheduleDismiss);
        toast.addEventListener('focusin', function () { window.clearTimeout(dismissTimer); });
        toast.addEventListener('focusout', scheduleDismiss);
        toast.querySelector('[data-toast-close]')?.addEventListener('click', dismissToast);
        scheduleDismiss();
    });

    const counterTargets = Array.from(document.querySelectorAll('.admin-metric strong, .account-stat strong, .mini-item span[data-count-up]'));
    if (!reducedMotion && 'IntersectionObserver' in window) {
        const counterObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                counterObserver.unobserve(entry.target);
                const target = entry.target;
                const original = target.textContent.trim();
                const match = original.match(/^(₹?)([\d,]+(?:\.\d+)?)(.*)$/);
                if (!match) return;
                const endValue = Number(match[2].replace(/,/g, ''));
                if (!Number.isFinite(endValue)) return;
                const prefix = match[1];
                const suffix = match[3];
                const startTime = performance.now();
                const duration = 1100;
                function tick(now) {
                    const progress = Math.min(1, (now - startTime) / duration);
                    const eased = 1 - Math.pow(1 - progress, 3);
                    const value = endValue * eased;
                    const formatted = Number.isInteger(endValue)
                        ? Math.round(value).toLocaleString('en-IN')
                        : value.toLocaleString('en-IN', { maximumFractionDigits: 2 });
                    target.textContent = `${prefix}${formatted}${suffix}`;
                    if (progress < 1) requestAnimationFrame(tick);
                    else target.textContent = original;
                }
                requestAnimationFrame(tick);
            });
        }, { threshold: 0.35 });
        counterTargets.forEach(function (target) { counterObserver.observe(target); });
    }

    window.SweetShopMotion = Object.freeze({
        springs: {
            snappy: { stiffness: 400, damping: 30 },
            smooth: { stiffness: 200, damping: 25 },
            bouncy: { stiffness: 300, damping: 10 },
            gentle: { stiffness: 100, damping: 15 }
        },
        tweens: {
            fast: { duration: 150, easing: 'cubic-bezier(0.25, 0.1, 0.25, 1)' },
            normal: { duration: 300, easing: 'cubic-bezier(0.25, 0.1, 0.25, 1)' },
            slow: { duration: 500, easing: 'cubic-bezier(0.25, 0.1, 0.25, 1)' },
            easeOut: { duration: 300, easing: 'cubic-bezier(0, 0, 0.2, 1)' }
        },
        reducedMotion: reducedMotion
    });

    window.SweetShopLoading = {
        showSkeleton: function (container, options) {
            if (!container || container.querySelector(':scope > .skeleton-overlay')) return;
            const settings = Object.assign({ rows: 3, type: 'card' }, options || {});
            const overlay = document.createElement('div');
            overlay.className = `skeleton-overlay skeleton-${settings.type}`;
            overlay.setAttribute('aria-hidden', 'true');
            for (let index = 0; index < settings.rows; index += 1) {
                const row = document.createElement('div');
                row.className = 'skeleton-card';
                row.innerHTML = '<span class="skeleton-block skeleton-media"></span><span class="skeleton-block skeleton-line"></span><span class="skeleton-block skeleton-line short"></span>';
                overlay.appendChild(row);
            }
            container.setAttribute('aria-busy', 'true');
            container.classList.add('has-skeleton');
            container.appendChild(overlay);
        },
        hideSkeleton: function (container) {
            if (!container) return;
            container.querySelector(':scope > .skeleton-overlay')?.remove();
            container.classList.remove('has-skeleton');
            container.removeAttribute('aria-busy');
        },
        spinner: function (size, label) {
            const spinner = document.createElement('span');
            spinner.className = `ui-spinner spinner-${size || 'medium'}`;
            spinner.setAttribute('role', 'status');
            spinner.setAttribute('aria-label', label || 'Loading');
            return spinner;
        }
    };

    const pageRoot = document.querySelector('[data-page-root]');
    const progressBar = document.querySelector('[data-page-progress]');
    if (pageRoot && progressBar) {
        const previousTransition = sessionStorage.getItem('sweet-shop-transition') || 'main';
        sessionStorage.removeItem('sweet-shop-transition');
        pageRoot.classList.add(`page-enter-${previousTransition}`);
        window.setTimeout(function () { pageRoot.classList.remove(`page-enter-${previousTransition}`); }, reducedMotion ? 0 : 320);

        let progressTimer;
        function startPageProgress() {
            window.clearTimeout(progressTimer);
            progressTimer = window.setTimeout(function () { progressBar.classList.add('is-loading'); }, 300);
        }
        document.addEventListener('click', function (event) {
            const link = event.target.closest('a[href]');
            if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            if (link.target === '_blank' || link.hasAttribute('download')) return;
            const destination = new URL(link.href, window.location.href);
            if (destination.origin !== window.location.origin || (destination.pathname === location.pathname && destination.search === location.search && destination.hash)) return;
            const currentIsDetail = /^\/products\/\d+/.test(location.pathname);
            const nextIsDetail = /^\/products\/\d+/.test(destination.pathname);
            const transition = nextIsDetail && !currentIsDetail ? 'detail' : currentIsDetail && !nextIsDetail ? 'back' : 'main';
            sessionStorage.setItem('sweet-shop-transition', transition);
            startPageProgress();
            if (pageRoot && !reducedMotion && destination.pathname !== location.pathname) {
                event.preventDefault();
                pageRoot.classList.add(`page-exit-${transition}`);
                window.setTimeout(function () { window.location.assign(destination.href); }, 150);
            }
        });
        window.addEventListener('pageshow', function () {
            window.clearTimeout(progressTimer);
            progressBar.classList.remove('is-loading');
            progressBar.classList.add('is-complete');
            window.setTimeout(function () { progressBar.classList.remove('is-complete'); }, reducedMotion ? 0 : 220);
        });

        let scrollFrame = 0;
        function updateScrollProgress() {
            if (scrollFrame) return;
            scrollFrame = requestAnimationFrame(function () {
                const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
                const progress = maxScroll > 0 ? Math.min(1, window.scrollY / maxScroll) : 0;
                progressBar.style.setProperty('--scroll-progress', progress);
                scrollFrame = 0;
            });
        }
        window.addEventListener('scroll', updateScrollProgress, { passive: true });
        updateScrollProgress();
    }

    const parallaxItems = Array.from(document.querySelectorAll('[data-parallax]'));
    if (!reducedMotion && window.innerWidth > 767 && parallaxItems.length && 'IntersectionObserver' in window) {
        const activeParallax = new Set();
        let parallaxFrame = 0;
        function updateParallax() {
            if (parallaxFrame) return;
            parallaxFrame = requestAnimationFrame(function () {
                activeParallax.forEach(function (image) {
                    const rect = image.parentElement.getBoundingClientRect();
                    const ratio = Number(image.dataset.parallax) || 0.3;
                    const offset = Math.max(-18, Math.min(18, (rect.top + rect.height / 2 - window.innerHeight / 2) * ratio * -0.08));
                    image.style.transform = `translate3d(0, ${offset}px, 0) scale(1.04)`;
                });
                parallaxFrame = 0;
            });
        }
        const parallaxObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    activeParallax.add(entry.target);
                    entry.target.style.willChange = 'transform';
                } else {
                    activeParallax.delete(entry.target);
                    entry.target.style.willChange = '';
                }
            });
            updateParallax();
        }, { rootMargin: '60px' });
        parallaxItems.forEach(function (image) { parallaxObserver.observe(image); });
        window.addEventListener('scroll', updateParallax, { passive: true });
        window.addEventListener('resize', updateParallax, { passive: true });
    }

    const chartBars = document.querySelectorAll('.admin-bars');
    if (!reducedMotion && 'IntersectionObserver' in window && chartBars.length) {
        const chartObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-chart-visible');
                chartObserver.unobserve(entry.target);
            });
        }, { threshold: 0.2, rootMargin: '0px 0px -10% 0px' });
        chartBars.forEach(function (chart) { chartObserver.observe(chart); });
    } else {
        chartBars.forEach(function (chart) { chart.classList.add('is-chart-visible'); });
    }

    document.querySelectorAll('[data-validate-form], [data-loading-form], .review-form, .profile-form').forEach(function (form) {
        form.noValidate = true;
        const fields = Array.from(form.querySelectorAll('input, select, textarea')).filter(function (field) {
            return field.willValidate && field.type !== 'hidden' && field.type !== 'submit';
        });

        function updateFieldError(field, force) {
            const label = field.closest('label');
            if (!force && !field.dataset.validationShown) return field.validity.valid;
            field.dataset.validationShown = 'true';
            let error = form.querySelector(`#${CSS.escape(field.id)}-error`);
            if (field.validity.valid) {
                field.removeAttribute('aria-invalid');
                field.removeAttribute('aria-errormessage');
                label?.classList.remove('has-error');
                label?.classList.toggle('has-valid', Boolean(field.value));
                if (error) error.remove();
                return true;
            }
            if (!field.id) field.id = `field-${Math.random().toString(36).slice(2, 9)}`;
            error = form.querySelector(`#${CSS.escape(field.id)}-error`);
            if (!error) {
                error = document.createElement('span');
                error.id = `${field.id}-error`;
                error.className = 'field-error';
                error.setAttribute('role', 'alert');
                const anchor = field.closest('.password-control') || field;
                anchor.insertAdjacentElement('afterend', error);
            }
            error.textContent = field.validity.valueMissing
                ? 'This field is required.'
                : field.validity.tooShort
                    ? `Please enter at least ${field.minLength} characters.`
                    : field.validity.typeMismatch
                        ? 'Enter a valid email address.'
                        : field.validationMessage;
            field.setAttribute('aria-invalid', 'true');
            field.setAttribute('aria-describedby', error.id);
            field.setAttribute('aria-errormessage', error.id);
            label?.classList.remove('has-valid');
            label?.classList.add('has-error');
            return false;
        }

        fields.forEach(function (field) {
            if (field.maxLength > 0) {
                const counter = document.createElement('small');
                counter.className = 'character-count';
                counter.setAttribute('aria-live', 'polite');
                field.insertAdjacentElement('afterend', counter);
                const updateCount = function () {
                    counter.textContent = `${field.value.length} / ${field.maxLength}`;
                    counter.classList.toggle('is-near-limit', field.value.length >= field.maxLength * 0.9);
                    counter.classList.toggle('is-at-limit', field.value.length >= field.maxLength);
                };
                field.addEventListener('input', updateCount);
                updateCount();
            }
            field.addEventListener('blur', function () { updateFieldError(field, true); });
            field.addEventListener('input', function () {
                if (field.dataset.validationShown) updateFieldError(field, true);
            });
            field.addEventListener('change', function () {
                if (field.dataset.validationShown) updateFieldError(field, true);
            });
        });
        form.addEventListener('submit', function (event) {
            const invalidFields = fields.filter(function (field) { return !updateFieldError(field, true); });
            if (invalidFields.length) {
                event.preventDefault();
                let alert = form.querySelector('.form-error-alert');
                if (!alert) {
                    alert = document.createElement('div');
                    alert.className = 'form-error-alert';
                    alert.setAttribute('role', 'alert');
                    alert.innerHTML = '<span aria-hidden="true">!</span><p>Check the highlighted fields and try again.</p><button type="button" aria-label="Dismiss error">×</button>';
                    form.prepend(alert);
                    alert.querySelector('button').addEventListener('click', function () { alert.remove(); });
                }
                form.classList.remove('has-validation-error');
                void form.offsetWidth;
                form.classList.add('has-validation-error');
                invalidFields[0].focus();
                invalidFields[0].scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'center' });
                return;
            }
            form.querySelector('.form-error-alert')?.remove();
            if (form.matches('[data-loading-form]') || form.matches('[data-auth-form]')) {
                form.setAttribute('aria-busy', 'true');
                const submit = form.querySelector('.auth-submit, button[type="submit"]');
                if (submit) {
                    submit.disabled = true;
                    submit.setAttribute('aria-busy', 'true');
                    if (form.matches('[data-auth-form]')) {
                        submit.classList.add('is-loading');
                    } else {
                        submit.classList.add('button-is-loading');
                        submit.insertAdjacentElement('afterbegin', window.SweetShopLoading.spinner('small', 'Submitting'));
                    }
                }
            }
        });
    });

    document.querySelectorAll('.btn').forEach(function (button) {
        button.addEventListener('pointerdown', function (event) {
            if (reducedMotion || button.matches(':disabled')) return;
            const rect = button.getBoundingClientRect();
            const ripple = document.createElement('span');
            ripple.className = 'button-ripple';
            ripple.style.left = `${event.clientX - rect.left}px`;
            ripple.style.top = `${event.clientY - rect.top}px`;
            button.appendChild(ripple);
            ripple.addEventListener('animationend', function () { ripple.remove(); }, { once: true });
        });
    });
});
