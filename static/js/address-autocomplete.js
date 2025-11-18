/**
 * ADDRESS AUTOCOMPLETE - SEPOMEX Integration
 *
 * Autocompletado de domicilio fiscal:
 * 1. 📮 Código Postal → SEPOMEX DB (oficial SAT)
 *    - Auto-completa: Municipio, Estado, Colonias
 *    - Validación contra base oficial
 *
 * @version 1.3 - Removed OSM/GPS (simplified)
 */

'use strict';

(function() {

    // ========================================
    // 1. POSTAL CODE SERVICE (SEPOMEX)
    // ========================================

    const PostalCodeService = {
        async lookup(codigoPostal) {
            try {
                const response = await fetch('/api/address/postal-code/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ codigo_postal: codigoPostal })
                });

                // BUG FIX #43: Verificar response.ok antes de parsear JSON
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                return data;

            } catch (error) {
                console.error('Postal code lookup error:', error);
                return { success: false, error: error.message };
            }
        },

        async autoFillFromCP(cp, options = {}) {
            const { showToast: shouldShowToast = true } = options;

            if (!cp || cp.length !== 5) {
                return;
            }

            // Mostrar loading en el campo
            const cpInput = document.getElementById('id_codigo_postal');
            if (cpInput) {
                cpInput.classList.add('is-validating');
            }

            try {
                const result = await this.lookup(cp);

                if (cpInput) {
                    cpInput.classList.remove('is-validating');
                }

                if (result.success) {
                    // Fill municipio y estado
                    AddressUI.fillMunicipio(result.municipio);
                    AddressUI.fillEstado(result.estado);

                    // Fill colonias select
                    AddressUI.fillColoniasSelect(result.colonias);

                    // Solo mostrar toast si no viene de recarga
                    if (shouldShowToast && typeof showToast !== 'undefined') {
                        if (result.municipio && result.estado) {
                            showToast(`✓ ${result.municipio}, ${result.estado}`, 'success');
                        }
                    }

                    if (cpInput) cpInput.classList.add('is-valid');

                    return true;
                } else {
                    if (cpInput) cpInput.classList.add('is-invalid');

                    // Solo mostrar error toast si no viene de GPS
                    if (shouldShowToast && typeof showToast !== 'undefined') {
                        showToast(result.error || 'Código postal no encontrado', 'error');
                    }

                    return false;
                }

            } catch (error) {
                if (cpInput) {
                    cpInput.classList.remove('is-validating');
                    cpInput.classList.add('is-invalid');
                }

                console.error('CP autofill error:', error);
                return false;
            }
        }
    };

    // ========================================
    // 2. UI HELPERS
    // ========================================

    const AddressUI = {
        async fillAll(addressData, options = {}) {
            const { fromGPS = false } = options;

            // 1. Fill código postal primero
            if (addressData.codigo_postal) {
                this.fillCodigoPostal(addressData.codigo_postal);

                // 2. Trigger postal code lookup para cargar colonias
                // Pasar showToast: false cuando viene de GPS para evitar duplicados
                if (typeof PostalCodeService !== 'undefined') {
                    await PostalCodeService.autoFillFromCP(addressData.codigo_postal, {
                        showToast: !fromGPS
                    });
                }
            }

            // 3. Ahora sí, fill colonia (después de que se cargaron las opciones)
            if (addressData.colonia) {
                // Small delay para que el select se populate
                setTimeout(() => {
                    this.fillColoniaValue(addressData.colonia);
                }, 500);
            }

            // 4. Fill resto de campos
            if (addressData.municipio) this.fillMunicipio(addressData.municipio);
            if (addressData.estado) this.fillEstado(addressData.estado);
            if (addressData.calle) this.fillCalle(addressData.calle);
            if (addressData.numero_exterior || addressData.numero) {
                this.fillNumeroExterior(addressData.numero_exterior || addressData.numero);
            }
        },

        fillCodigoPostal(cp) {
            const input = document.getElementById('id_codigo_postal');
            if (input) {
                input.value = cp;
                input.classList.add('is-valid');
            }
        },

        fillColoniasSelect(colonias) {
            const select = document.getElementById('id_colonia_select');
            if (!select) return;

            select.innerHTML = '<option value="">Selecciona tu colonia</option>';

            // Agregar colonias oficiales
            colonias.forEach(colonia => {
                const option = document.createElement('option');
                option.value = colonia;
                option.textContent = colonia;
                select.appendChild(option);
            });

            // ✅ AGREGAR OPCIÓN "OTRA" al final
            const optionOtra = document.createElement('option');
            optionOtra.value = '__CUSTOM__';
            optionOtra.textContent = '➕ Otra (escribir manualmente)';
            optionOtra.style.fontWeight = '600';
            optionOtra.style.borderTop = '1px solid #e5e7eb';
            select.appendChild(optionOtra);

            select.disabled = false;
            select.classList.remove('is-invalid');

            // Event listener para detectar "Otra"
            select.addEventListener('change', function() {
                if (this.value === '__CUSTOM__') {
                    AddressUI.showCustomColoniaInput();
                } else if (this.value) {
                    AddressUI.hideCustomColoniaInput();
                    AddressUI.setColoniaValue(this.value);
                }
            });
        },

        showCustomColoniaInput() {
            const select = document.getElementById('id_colonia_select');
            const customInput = document.getElementById('id_colonia_custom');
            const backBtn = document.getElementById('btnBackToSelect');
            const helpText = document.getElementById('coloniaHelpText');

            if (select) select.style.display = 'none';
            if (customInput) {
                customInput.style.display = 'block';
                customInput.focus();
            }
            if (backBtn) backBtn.style.display = 'block';
            if (helpText) helpText.textContent = 'Escribe el nombre exacto de tu colonia';

            // Limpiar hidden field
            const hiddenField = document.getElementById('id_colonia');
            if (hiddenField) hiddenField.value = '';

            if (typeof showToast !== 'undefined') {
                showToast('💡 Escribe el nombre de tu colonia manualmente', 'info');
            }
        },

        hideCustomColoniaInput() {
            const select = document.getElementById('id_colonia_select');
            const customInput = document.getElementById('id_colonia_custom');
            const backBtn = document.getElementById('btnBackToSelect');
            const helpText = document.getElementById('coloniaHelpText');

            if (select) select.style.display = 'block';
            if (customInput) {
                customInput.style.display = 'none';
                customInput.value = '';
            }
            if (backBtn) backBtn.style.display = 'none';
            if (helpText) helpText.textContent = 'Selecciona de la lista';
        },

        setColoniaValue(colonia) {
            const hiddenField = document.getElementById('id_colonia');
            if (hiddenField) {
                hiddenField.value = colonia;
            }
        },

        fillColoniaValue(colonia) {
            if (!colonia) return;

            // Usar el SELECT visible, no el hidden input
            const select = document.getElementById('id_colonia_select');
            const hiddenInput = document.getElementById('id_colonia');

            if (!select || !hiddenInput) {
                console.warn('⚠️ Colonia select elements not found');
                return;
            }

            // Si el select tiene opciones, buscar la colonia
            if (select.options && select.options.length > 0) {
                const option = Array.from(select.options).find(opt =>
                    opt.value === colonia || opt.text === colonia
                );

                if (option) {
                    select.value = option.value;
                    hiddenInput.value = option.value;
                    select.classList.add('is-valid');
                } else {
                    // Si no está en la lista, usar custom input
                    const customInput = document.getElementById('id_colonia_custom');
                    if (customInput) {
                        customInput.value = colonia;
                        hiddenInput.value = colonia;
                        // Switch to custom input
                        select.style.display = 'none';
                        customInput.style.display = 'block';
                    }
                }
            } else {
                // Select no tiene opciones aún, usar custom input directamente
                const customInput = document.getElementById('id_colonia_custom');
                if (customInput) {
                    customInput.value = colonia;
                    hiddenInput.value = colonia;
                    select.style.display = 'none';
                    customInput.style.display = 'block';
                }
            }
        },

        fillMunicipio(municipio) {
            const input = document.getElementById('id_municipio');
            if (input) {
                input.value = municipio;
                input.classList.add('is-valid');
            }
        },

        fillEstado(estado) {
            const input = document.getElementById('id_estado');
            if (input) {
                input.value = estado;
                input.classList.add('is-valid');
            }
        },

        fillCalle(calle) {
            const input = document.getElementById('id_calle');
            if (input) {
                input.value = calle;
                input.classList.add('is-valid');
            }
        },

        fillNumeroExterior(numero) {
            const input = document.getElementById('id_numero_exterior');
            if (input) {
                input.value = numero;
                input.classList.add('is-valid');
            }
        },

        showCPHint(municipio, estado) {
            const hint = document.getElementById('cpLocationHint');
            if (hint) {
                hint.textContent = `📍 ${municipio}, ${estado}`;
                hint.style.color = '#15803d';
                hint.style.fontWeight = '600';
            }
        },

        /**
         * ✅ NUEVO: Actualizar vista previa del domicilio completo
         */
        updateAddressPreview() {
            const preview = document.getElementById('addressPreview');
            const previewText = document.getElementById('addressPreviewText');

            if (!preview || !previewText) return;

            // Obtener valores de todos los campos
            const calle = document.getElementById('id_calle')?.value || '';
            const numExt = document.getElementById('id_numero_exterior')?.value || '';
            const numInt = document.getElementById('id_numero_interior')?.value || '';
            const colonia = document.getElementById('id_colonia')?.value || '';
            const municipio = document.getElementById('id_municipio')?.value || '';
            const estado = document.getElementById('id_estado')?.value || '';
            const cp = document.getElementById('id_codigo_postal')?.value || '';

            // Verificar que tenemos los campos mínimos
            if (calle && numExt && colonia && municipio && estado && cp) {
                // Formatear dirección
                const direccion = [
                    `${calle} ${numExt}${numInt ? ', ' + numInt : ''}`,
                    `Colonia ${colonia}`,
                    `${municipio}, ${estado}`,
                    `C.P. ${cp}`
                ].join('\n');

                previewText.textContent = direccion;
                preview.style.display = 'block';

                // Smooth scroll into view si no está visible
                if (!this.isElementInViewport(preview)) {
                    preview.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            } else {
                preview.style.display = 'none';
            }
        },

        /**
         * Helper: Check if element is in viewport
         */
        isElementInViewport(el) {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            return (
                rect.top >= 0 &&
                rect.left >= 0 &&
                rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                rect.right <= (window.innerWidth || document.documentElement.clientWidth)
            );
        }
    };

    // ========================================
    // 5. EVENT LISTENERS
    // ========================================

    function initGPSButton() {
        const gpsBtn = document.getElementById('btnUseGPS');
        if (!gpsBtn) return;

        gpsBtn.addEventListener('click', async function(e) {
            e.preventDefault();

            // Loading state
            const originalHTML = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Obteniendo ubicación...';
            this.disabled = true;

            const success = await GeolocationService.autoFillFromGPS();

            // Reset button
            this.innerHTML = originalHTML;
            this.disabled = false;
        });

        console.log('✅ GPS button initialized');
    }

    function initPostalCodeAutocomplete() {
        const cpInput = document.getElementById('id_codigo_postal');
        if (!cpInput) return;

        cpInput.addEventListener('blur', async function() {
            const cp = this.value.trim();

            if (cp.length === 5) {
                await PostalCodeService.autoFillFromCP(cp);
            }
        });

        // Solo números
        cpInput.addEventListener('input', function() {
            this.value = this.value.replace(/[^0-9]/g, '');

            // Limpiar validación si empieza a escribir de nuevo
            if (this.classList.contains('is-invalid') || this.classList.contains('is-valid')) {
                this.classList.remove('is-invalid', 'is-valid');
            }
        });

        console.log('✅ Postal code autocomplete initialized');
    }

    function initCustomColoniaHandlers() {
        // Event listener para input custom
        const customInput = document.getElementById('id_colonia_custom');
        if (customInput) {
            customInput.addEventListener('input', function() {
                const hiddenField = document.getElementById('id_colonia');
                if (hiddenField) {
                    hiddenField.value = this.value;
                }
            });

            // BUG FIX #7: Validar colonia custom contra SEPOMEX en blur
            customInput.addEventListener('blur', async function() {
                const coloniaValue = this.value.trim();
                if (!coloniaValue) return;

                // Obtener colonias válidas del select
                const coloniaSelect = document.getElementById('id_colonia_select');
                const validColonias = [];
                if (coloniaSelect && coloniaSelect.options) {
                    for (let option of coloniaSelect.options) {
                        if (option.value && option.value !== '__CUSTOM__') {
                            validColonias.push(option.value.toLowerCase());
                        }
                    }
                }

                // Validar si la colonia custom está en la lista de SEPOMEX
                const isValidColonia = validColonias.includes(coloniaValue.toLowerCase());

                if (!isValidColonia && validColonias.length > 0) {
                    // Warning (no error) si no está en SEPOMEX
                    this.classList.remove('is-valid');
                    this.classList.add('is-warning');

                    if (typeof showToast !== 'undefined') {
                        showToast(`⚠️ "${coloniaValue}" no está en el catálogo SEPOMEX para este CP. Verifica que esté correcta.`, 'warning');
                    }
                } else {
                    this.classList.add('is-valid');
                    this.classList.remove('is-invalid', 'is-warning');
                }
            });
        }

        // Event listener para botón "Volver a lista"
        const backBtn = document.getElementById('btnBackToSelect');
        if (backBtn) {
            backBtn.addEventListener('click', function(e) {
                e.preventDefault();
                AddressUI.hideCustomColoniaInput();

                // Reset select a default
                const select = document.getElementById('id_colonia_select');
                if (select) {
                    select.value = '';
                }
            });
        }

        console.log('✅ Custom colonia handlers initialized');
    }

    function initStreetAutocomplete() {
        const calleInput = document.getElementById('id_calle');
        if (!calleInput) return;

        calleInput.addEventListener('input', function() {
            const query = this.value.trim();

            clearTimeout(StreetAutocompleteService.debounceTimer);

            if (query.length < 3) {
                StreetAutocompleteService.hideSuggestions(this);
                return;
            }

            // Debounce
            StreetAutocompleteService.debounceTimer = setTimeout(async () => {
                const cp = document.getElementById('id_codigo_postal')?.value;
                const colonia = document.getElementById('id_colonia')?.value;

                const suggestions = await StreetAutocompleteService.suggest(query, cp, colonia);
                StreetAutocompleteService.showSuggestions(calleInput, suggestions);
            }, 500);
        });

        calleInput.addEventListener('blur', function() {
            StreetAutocompleteService.hideSuggestions(this);
        });

        console.log('✅ Street autocomplete initialized');
    }

    // ========================================
    // 6. UTILS
    // ========================================

    function getCsrfToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfInput ? csrfInput.value : '';
    }

    // ========================================
    // 3. INITIALIZATION
    // ========================================

    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        try {
            initPostalCodeAutocomplete();
            initCustomColoniaHandlers();

            // Si el CP ya tiene valor al cargar (edición), trigger lookup
            const cpInput = document.getElementById('id_codigo_postal');
            if (cpInput && cpInput.value && cpInput.value.length === 5) {
                console.log('📮 CP prellenado detectado, cargando colonias...');
                PostalCodeService.autoFillFromCP(cpInput.value, { showToast: false });
            }

            console.log('✅ Address autocomplete (SEPOMEX only) initialized');
        } catch (error) {
            console.error('❌ Address Autocomplete initialization error:', error);
        }
    }

    // Auto-initialize
    init();

    // Export for debugging
    window.AddressAutocomplete = {
        PostalCode: PostalCodeService,
        UI: AddressUI
    };

})();
