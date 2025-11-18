/**
 * Kita Link Actions - Centralized JavaScript functions
 * Used across all sections: dashboard, links, reports, etc.
 */

// Global Link Actions
window.KitaLinkActions = {

    // Show detail panel (works from any section)
    showDetailPanel: function(type, id) {
        console.log('showDetailPanel called with:', type, id);

        fetch(`/panel/detalle/${type}/${id}/`)
            .then(response => response.text())
            .then(html => {
                document.getElementById('detail-panel-content').innerHTML = html;
                document.getElementById('detailPanelTitle').textContent = 'Detalles';
                const offcanvas = new bootstrap.Offcanvas(document.getElementById('detailPanel'));
                offcanvas.show();

                // Initialize link features after panel opens
                if (type === 'link') {
                    setTimeout(() => {
                        this.initLinkFeatures(id);
                    }, 500);
                }
            })
            .catch(error => {
                console.error('Error loading detail panel:', error);
                showToast('Error cargando detalles', 'error');
            });
    },

    // Initialize link-specific features (chart, etc.)
    initLinkFeatures: function(linkId) {
        // Initialize views timeline chart
        this.initViewsTimeline(linkId);
    },

    // Views Timeline Chart
    initViewsTimeline: function(linkId) {
        const canvas = document.getElementById(`linkViewsChart-${linkId}`);
        if (!canvas) return;

        const loading = document.getElementById(`linkViewsLoading-${linkId}`);
        if (loading) loading.style.display = 'flex';

        fetch(`/panel/api/link-views/${linkId}/`)
            .then(response => response.json())
            .then(data => {
                if (loading) loading.style.display = 'none';

                if (!data.success) {
                    console.error('Error loading link views:', data.error);
                    return;
                }

                new Chart(canvas, {
                    type: 'line',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            label: 'Vistas',
                            data: data.data,
                            borderColor: '#046865',
                            backgroundColor: 'rgba(4, 104, 101, 0.1)',
                            tension: 0.3,
                            fill: true,
                            pointBackgroundColor: '#046865',
                            pointBorderColor: '#f1f5f9',
                            pointBorderWidth: 2,
                            pointRadius: 3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            intersect: false,
                            mode: 'index'
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                enabled: true,
                                mode: 'index',
                                intersect: false,
                                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                                titleColor: '#f1f5f9',
                                bodyColor: '#f1f5f9',
                                borderColor: 'rgba(71, 85, 105, 0.4)',
                                borderWidth: 1,
                                cornerRadius: 8,
                                padding: 12,
                                callbacks: {
                                    label: function(context) {
                                        return `${context.parsed.y} vistas`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: {
                                    color: 'rgba(241, 245, 249, 0.1)',
                                    borderColor: 'rgba(241, 245, 249, 0.2)'
                                },
                                ticks: {
                                    color: '#94a3b8',
                                    font: { size: 10 },
                                    maxTicksLimit: 8
                                }
                            },
                            y: {
                                beginAtZero: true,
                                grid: {
                                    color: 'rgba(241, 245, 249, 0.1)',
                                    borderColor: 'rgba(241, 245, 249, 0.2)'
                                },
                                ticks: {
                                    color: '#94a3b8',
                                    font: { size: 10 },
                                    stepSize: 1
                                }
                            }
                        }
                    }
                });
            })
            .catch(error => {
                if (loading) loading.style.display = 'none';
                console.error('Error loading link views chart:', error);
            });
    },

    // Copy public URL
    copyPublicUrl: function() {
        const urlInput = document.getElementById('public-url');
        if (urlInput) {
            urlInput.select();
            navigator.clipboard.writeText(urlInput.value).then(function() {
                showToast('URL copiada al portapapeles', 'success');
            }, function(err) {
                showToast('Error al copiar URL', 'error');
            });
        }
    },

    // ⚠️ DEPRECATED - Función removida de la UI
    // Duplicate link
    duplicateLink: function(linkId) {
        console.warn('⚠️ DEPRECATED: duplicateLink() - Función removida de la UI');
        return;
        /* CÓDIGO COMENTADO - Conservado por si se necesita después
        console.log('🔄 Loading link data for duplication:', linkId);

        // Fetch link data first
        fetch(`/enlaces/editar-datos/${linkId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.showDuplicateModal(data.link);
                } else {
                    showToast('Error cargando datos del link', 'error');
                }
            })
            .catch(error => {
                console.error('Error loading link data:', error);
                showToast('Error de conexión', 'error');
            });
    },

    // Show duplicate modal with preview + customization
    showDuplicateModal: function(linkData) {
        console.log('📋 Showing duplicate modal for:', linkData);

        // Helper para escapar HTML
        const escapeHtml = (text) => {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        };

        // Formatear fechas
        const createdAt = new Date(linkData.created_at);
        const expiresAt = new Date(linkData.expires_at);
        const createdFormatted = createdAt.toLocaleDateString('es-MX', {
            day: 'numeric',
            month: 'short',
            year: 'numeric'
        });
        const expiresFormatted = expiresAt.toLocaleDateString('es-MX', {
            day: 'numeric',
            month: 'short',
            year: 'numeric'
        });

        // Calcular fechas de vigencia para el duplicado
        const now = new Date();
        const calcExpiry = (days) => {
            const d = new Date(now.getTime() + days * 86400000);
            return d.toLocaleDateString('es-MX', {day: 'numeric', month: 'short'});
        };

        // Create duplicate modal
        const duplicateModal = document.createElement('div');
        duplicateModal.className = 'modal fade';
        duplicateModal.id = 'duplicateLinkModal';
        duplicateModal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="iconoir-copy me-2"></i>
                            Duplicar Link de Pago
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar modal"></button>
                    </div>
                    <div class="modal-body">
                        <!-- Link Original Preview -->
                        <div class="alert alert-secondary mb-4">
                            <h6 class="mb-3">
                                <i class="iconoir-page me-2"></i>
                                Link Original
                            </h6>
                            <div class="row small">
                                <div class="col-md-6 mb-2">
                                    <strong>Título:</strong><br>
                                    ${escapeHtml(linkData.title)}
                                </div>
                                <div class="col-md-6 mb-2">
                                    <strong>Monto:</strong><br>
                                    $${parseFloat(linkData.amount).toLocaleString('es-MX', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MXN
                                </div>
                                ${linkData.customer_name || linkData.customer_email ? `
                                <div class="col-md-6 mb-2">
                                    <strong>Cliente:</strong><br>
                                    ${escapeHtml(linkData.customer_name || linkData.customer_email)}
                                </div>
                                ` : ''}
                                <div class="col-md-6 mb-2">
                                    <strong>Creado:</strong> ${createdFormatted}<br>
                                    <strong>Expira:</strong> ${expiresFormatted}
                                </div>
                            </div>
                        </div>

                        <!-- Personalización del Duplicado -->
                        <h6 class="mb-3">
                            <i class="iconoir-edit-pencil me-2"></i>
                            Personalizar Duplicado
                        </h6>

                        <form id="duplicateLinkForm" novalidate>
                            <input type="hidden" name="link_id" value="${linkData.id}">

                            <!-- Título -->
                            <div class="mb-3">
                                <label for="duplicate-title" class="form-label">
                                    Título del nuevo link <span class="text-danger">*</span>
                                </label>
                                <input type="text"
                                       class="form-control"
                                       id="duplicate-title"
                                       name="title"
                                       value="${escapeHtml(linkData.title)} (Copia)"
                                       required
                                       minlength="3"
                                       maxlength="255"
                                       autofocus
                                       placeholder="Ej: Factura #002"
                                       aria-required="true">
                                <small class="form-text text-muted">
                                    Puedes modificar el título para diferenciarlo del original
                                </small>
                            </div>

                            <!-- Vigencia -->
                            <div class="mb-3">
                                <label class="form-label">
                                    Vigencia del nuevo link <span class="text-danger">*</span>
                                </label>
                                <div class="timing-pills">
                                    <button type="button" class="timing-pill" data-days="1" onclick="selectDuplicateValidity(1)">
                                        1 día (${calcExpiry(1)})
                                    </button>
                                    <button type="button" class="timing-pill active" data-days="3" onclick="selectDuplicateValidity(3)">
                                        3 días (${calcExpiry(3)})
                                    </button>
                                    <button type="button" class="timing-pill" data-days="7" onclick="selectDuplicateValidity(7)">
                                        7 días (${calcExpiry(7)})
                                    </button>
                                    <button type="button" class="timing-pill" data-days="30" onclick="selectDuplicateValidity(30)">
                                        30 días (${calcExpiry(30)})
                                    </button>
                                </div>
                                <input type="hidden" id="duplicate-validity" name="validity_days" value="3">
                                <small class="form-text text-muted mt-2 d-block">
                                    <i class="iconoir-calendar me-1"></i>
                                    El nuevo link expirará el <strong id="duplicate-expiry-date">${calcExpiry(3)}</strong>
                                </small>
                            </div>

                            <!-- Opciones de Copia -->
                            <div class="mb-3">
                                <label class="form-label">Opciones de Copia</label>

                                <div class="form-check">
                                    <input class="form-check-input"
                                           type="checkbox"
                                           id="duplicate-copy-notifications"
                                           name="copy_notifications"
                                           checked>
                                    <label class="form-check-label" for="duplicate-copy-notifications">
                                        <strong>Copiar configuración de notificaciones</strong>
                                    </label>
                                    <div class="form-text">
                                        Mantiene recordatorios y alertas configuradas
                                    </div>
                                </div>

                                <div class="form-check mt-2">
                                    <input class="form-check-input"
                                           type="checkbox"
                                           id="duplicate-keep-customer"
                                           name="keep_customer_data"
                                           checked
                                           onchange="toggleCustomerWarning()">
                                    <label class="form-check-label" for="duplicate-keep-customer">
                                        <strong>Mantener datos del cliente</strong>
                                    </label>
                                    <div class="form-text">
                                        Copia nombre y email del cliente original
                                    </div>
                                </div>
                            </div>

                            ${linkData.customer_email ? `
                            <!-- Warning Email Cliente -->
                            <div class="alert alert-warning d-flex align-items-start gap-2" id="customer-email-warning">
                                <i class="iconoir-warning-triangle" style="margin-top: 2px;"></i>
                                <div>
                                    <strong>⚠️ Atención: Email del cliente</strong>
                                    <p class="mb-0 small">
                                        El email <strong>${escapeHtml(linkData.customer_email)}</strong> se copiará al nuevo link.
                                        Si este duplicado es para otro cliente, desmarca "Mantener datos del cliente" o edita el link después.
                                    </p>
                                </div>
                            </div>
                            ` : ''}
                        </form>
                    </div>
                    <div class="modal-footer">
                        <div class="d-flex justify-content-between w-100">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                Cancelar
                            </button>
                            <button type="button" class="btn btn-primary" id="confirmDuplicateBtn">
                                <span class="btn-content">
                                    <i class="iconoir-copy me-2"></i>
                                    Duplicar Link
                                </span>
                                <span class="btn-loading d-none">
                                    <span class="spinner-border spinner-border-sm me-2"></span>
                                    Duplicando...
                                </span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(duplicateModal);
        const modal = new bootstrap.Modal(duplicateModal);
        modal.show();

        // Handler de confirmación
        document.getElementById('confirmDuplicateBtn').addEventListener('click', () => {
            this.performDuplicate(linkData.id, modal);
        });

        // Cleanup
        duplicateModal.addEventListener('hidden.bs.modal', () => {
            if (document.body.contains(duplicateModal)) {
                document.body.removeChild(duplicateModal);
            }
        });
    },

    // Perform duplication with custom params
    performDuplicate: function(linkId, confirmModal) {
        const form = document.getElementById('duplicateLinkForm');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        // Agregar checkboxes
        data.copy_notifications = document.getElementById('duplicate-copy-notifications')?.checked || false;
        data.keep_customer_data = document.getElementById('duplicate-keep-customer')?.checked || false;

        console.log('📦 Duplicating with params:', data);

        // Loading state
        const submitBtn = document.getElementById('confirmDuplicateBtn');
        const btnContent = submitBtn.querySelector('.btn-content');
        const btnLoading = submitBtn.querySelector('.btn-loading');

        if (btnContent) btnContent.classList.add('d-none');
        if (btnLoading) btnLoading.classList.remove('d-none');
        submitBtn.disabled = true;

        fetch('/enlaces/duplicar/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(responseData => {
            if (responseData.success) {
                // Cerrar modal de confirmación
                confirmModal.hide();

                // Cerrar detail panel si está abierto
                const offcanvas = bootstrap.Offcanvas.getInstance(document.getElementById('detailPanel'));
                if (offcanvas) offcanvas.hide();

                // Mostrar success modal
                setTimeout(() => {
                    this.showDuplicateSuccessModal(responseData);
                }, 300);

                // Update related data
                this.updateRelatedData();
            } else {
                showToast(responseData.error || 'Error duplicando link', 'error');
                if (btnContent) btnContent.classList.remove('d-none');
                if (btnLoading) btnLoading.classList.add('d-none');
                submitBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Duplicate error:', error);
            showToast('Error de conexión', 'error');
            if (btnContent) btnContent.classList.remove('d-none');
            if (btnLoading) btnLoading.classList.add('d-none');
            submitBtn.disabled = false;
        });
    },

    // Show success modal after duplication
    showDuplicateSuccessModal: function(responseData) {
        const successModal = document.createElement('div');
        successModal.className = 'modal fade';
        successModal.id = 'duplicateSuccessModal';
        successModal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header border-0 pb-0">
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <!-- Success Icon -->
                        <div class="mb-3">
                            <div style="font-size: 64px;">✅</div>
                        </div>

                        <h3 class="mb-2">¡Link Duplicado Exitosamente!</h3>
                        <p class="text-muted mb-4">Tu nuevo link de pago está listo</p>

                        <!-- Link Info Card -->
                        <div class="card border mb-4">
                            <div class="card-body text-start">
                                <h6 class="card-title">${responseData.title || 'Link de pago'}</h6>
                                <p class="text-muted mb-2">
                                    <i class="iconoir-dollar me-1"></i>
                                    $${parseFloat(responseData.amount || 0).toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN
                                </p>
                                <p class="text-muted small mb-0">
                                    <i class="iconoir-calendar me-1"></i>
                                    Expira: ${responseData.expires_at || ''}
                                </p>
                            </div>
                        </div>

                        <!-- URL Input -->
                        <div class="input-group mb-3">
                            <input type="text"
                                   class="form-control"
                                   id="duplicate-success-url"
                                   value="${responseData.public_url}"
                                   readonly
                                   onclick="this.select()">
                            <button class="btn btn-outline-secondary"
                                    type="button"
                                    onclick="copyDuplicateUrl()"
                                    title="Copiar URL">
                                <i class="iconoir-copy"></i>
                            </button>
                        </div>

                        <!-- Action Buttons -->
                        <div class="d-grid gap-2">
                            <button type="button"
                                    class="btn btn-primary"
                                    onclick="viewDuplicatedLink('${responseData.link_id}')">
                                <i class="iconoir-eye me-2"></i>
                                Ver Detalles del Nuevo Link
                            </button>
                            <button type="button"
                                    class="btn btn-outline-primary"
                                    onclick="editDuplicatedLink('${responseData.link_id}')">
                                <i class="iconoir-edit-pencil me-2"></i>
                                Editar Nuevo Link
                            </button>
                            <button type="button"
                                    class="btn btn-outline-secondary"
                                    data-bs-dismiss="modal">
                                Cerrar
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(successModal);
        const modal = new bootstrap.Modal(successModal);
        modal.show();

        // Cleanup
        successModal.addEventListener('hidden.bs.modal', () => {
            if (document.body.contains(successModal)) {
                document.body.removeChild(successModal);
            }
        });
        */
    },

    // Cancel link with confirmation modal
    cancelLink: function(linkId) {
        console.log('🗑️ Loading link data for cancellation:', linkId);

        // Fetch link data first
        fetch(`/enlaces/editar-datos/${linkId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.showCancelModal(data.link);
                } else {
                    showToast('Error cargando datos del link', 'error');
                }
            })
            .catch(error => {
                console.error('Error loading link data:', error);
                showToast('Error de conexión', 'error');
            });
    },

    // Show cancel confirmation modal
    showCancelModal: function(linkData) {
        console.log('⚠️ Showing cancel modal for:', linkData);

        const escapeHtml = (text) => {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        };

        const expiresAt = new Date(linkData.expires_at);
        const expiresFormatted = expiresAt.toLocaleDateString('es-MX', {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        const createdAt = new Date(linkData.created_at);
        const createdFormatted = createdAt.toLocaleDateString('es-MX', {
            day: 'numeric',
            month: 'short',
            year: 'numeric'
        });

        // Create cancel modal
        const cancelModal = document.createElement('div');
        cancelModal.className = 'modal fade';
        cancelModal.id = 'cancelLinkModal';
        cancelModal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-danger text-white">
                        <h5 class="modal-title">
                            <i class="iconoir-warning-triangle me-2"></i>
                            ¿Cancelar Link de Pago?
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Cerrar modal"></button>
                    </div>

                    <div class="modal-body">
                        <!-- Alerta de acción irreversible -->
                        <div class="alert alert-warning mb-4">
                            <strong>⚠️ Esta acción NO se puede deshacer</strong>
                        </div>

                        <!-- Detalles del Link -->
                        <div class="card mb-4">
                            <div class="card-body">
                                <h6 class="mb-3">Detalles del Link</h6>
                                <div class="row small">
                                    <div class="col-6 mb-2">
                                        <strong>Título:</strong><br>
                                        ${escapeHtml(linkData.title)}
                                    </div>
                                    <div class="col-6 mb-2">
                                        <strong>Monto:</strong><br>
                                        $${parseFloat(linkData.amount).toLocaleString('es-MX', {minimumFractionDigits: 2})} MXN
                                    </div>
                                    ${linkData.customer_name || linkData.customer_email ? `
                                    <div class="col-6 mb-2">
                                        <strong>Cliente:</strong><br>
                                        ${escapeHtml(linkData.customer_name || linkData.customer_email)}
                                    </div>
                                    ` : ''}
                                    <div class="col-6 mb-2">
                                        <strong>Creado:</strong> ${createdFormatted}<br>
                                        <strong>Expira:</strong> ${expiresFormatted}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Consecuencias -->
                        <h6 class="mb-2">Al cancelar este link:</h6>
                        <ul class="list-unstyled mb-4">
                            <li class="mb-1">🚫 El cliente NO podrá realizar el pago</li>
                            <li class="mb-1">📧 Se cancelarán recordatorios automáticos</li>
                            <li class="mb-1">📊 El link aparecerá como "Cancelado" en reportes</li>
                            <li class="mb-1">🔗 El enlace público quedará inaccesible</li>
                        </ul>

                        <form id="cancelLinkForm" novalidate>
                            <!-- Razón de Cancelación -->
                            <div class="mb-3">
                                <label for="cancel-reason" class="form-label">
                                    ¿Por qué cancelas este link? <span class="text-danger">*</span>
                                </label>
                                <select class="form-select" id="cancel-reason" name="cancellation_reason" required>
                                    <option value="">Selecciona una razón...</option>
                                    <option value="paid_other_method">Cliente pagó por otro medio</option>
                                    <option value="wrong_amount">Error en monto o descripción</option>
                                    <option value="customer_request">Cliente solicitó cancelación</option>
                                    <option value="duplicate">Link duplicado</option>
                                    <option value="expired_intent">Cliente ya no quiere pagar</option>
                                    <option value="other">Otra razón</option>
                                </select>
                            </div>

                            ${linkData.customer_email ? `
                            <!-- Notificar al cliente -->
                            <div class="form-check mb-3">
                                <input class="form-check-input" type="checkbox" id="notify-customer" name="notify_customer" checked>
                                <label class="form-check-label" for="notify-customer">
                                    Enviar email al cliente informando la cancelación
                                </label>
                                <div class="form-text">
                                    Se enviará a: <strong>${escapeHtml(linkData.customer_email)}</strong>
                                </div>
                            </div>
                            ` : ''}

                            <!-- Confirmación: Escribe CANCELAR -->
                            <div class="mb-3">
                                <label for="type-confirm" class="form-label text-danger">
                                    <strong>⚠️ Para confirmar, escribe <code>CANCELAR</code>:</strong>
                                </label>
                                <input type="text"
                                       class="form-control"
                                       id="type-confirm"
                                       placeholder="Escribe CANCELAR en mayúsculas"
                                       autocomplete="off"
                                       required>
                                <small class="form-text text-muted">
                                    Esto previene cancelaciones accidentales
                                </small>
                            </div>
                        </form>
                    </div>

                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            Volver
                        </button>
                        <button type="button" class="btn btn-danger" id="confirm-cancel-btn" disabled>
                            <span class="btn-content">
                                <i class="iconoir-xmark me-2"></i>
                                Cancelar Link
                            </span>
                            <span class="btn-loading d-none">
                                <span class="spinner-border spinner-border-sm me-2"></span>
                                Cancelando...
                            </span>
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(cancelModal);
        const modal = new bootstrap.Modal(cancelModal);
        modal.show();

        // Habilitar botón solo si selecciona razón Y escribe CANCELAR
        const reasonSelect = cancelModal.querySelector('#cancel-reason');
        const typeConfirm = cancelModal.querySelector('#type-confirm');
        const confirmBtn = cancelModal.querySelector('#confirm-cancel-btn');

        const validateForm = () => {
            const hasReason = reasonSelect.value !== '';
            const hasTyped = typeConfirm.value === 'CANCELAR';
            confirmBtn.disabled = !(hasReason && hasTyped);
        };

        reasonSelect.addEventListener('change', validateForm);
        typeConfirm.addEventListener('input', validateForm);

        // Handle confirm button
        confirmBtn.addEventListener('click', () => {
            this.executeCancelLink(linkData.id, modal);
        });

        // Cleanup
        cancelModal.addEventListener('hidden.bs.modal', () => {
            if (document.body.contains(cancelModal)) {
                document.body.removeChild(cancelModal);
            }
        });
    },

    // Execute link cancellation
    executeCancelLink: function(linkId, confirmModal) {
        const form = document.getElementById('cancelLinkForm');
        const reason = document.getElementById('cancel-reason').value;
        const notifyCustomer = document.getElementById('notify-customer')?.checked || false;

        console.log('🗑️ Cancelling link:', { linkId, reason, notifyCustomer });

        // Loading state
        const confirmBtn = document.getElementById('confirm-cancel-btn');
        const btnContent = confirmBtn.querySelector('.btn-content');
        const btnLoading = confirmBtn.querySelector('.btn-loading');

        if (btnContent) btnContent.classList.add('d-none');
        if (btnLoading) btnLoading.classList.remove('d-none');
        confirmBtn.disabled = true;

        fetch('/enlaces/cancelar/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                link_id: linkId,
                cancellation_reason: reason,
                notify_customer: notifyCustomer
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Close modal
                confirmModal.hide();

                // Success toast
                showToast('Link cancelado exitosamente', 'success');

                // Update UI
                this.updateRelatedData();

                // Close detail panel
                const offcanvas = bootstrap.Offcanvas.getInstance(document.getElementById('detailPanel'));
                if (offcanvas) offcanvas.hide();
            } else {
                showToast(data.error || 'Error cancelando link', 'error');
                if (btnContent) btnContent.classList.remove('d-none');
                if (btnLoading) btnLoading.classList.add('d-none');
                confirmBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('Cancel link error:', error);
            showToast('Error de conexión', 'error');
            if (btnContent) btnContent.classList.remove('d-none');
            if (btnLoading) btnLoading.classList.add('d-none');
            confirmBtn.disabled = false;
        });
    },

    // ⚠️ DEPRECATED - Función removida de la UI (recordatorios automáticos vía Celery)
    // Send reminder
    sendReminder: function(linkId) {
        console.warn('⚠️ DEPRECATED: sendReminder() - Función removida de la UI. Los recordatorios se envían automáticamente vía Celery');
        return;
    },

    // Edit link modal
    showEditLinkModal: function(linkId) {
        fetch(`/enlaces/editar-datos/${linkId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Close detail panel first
                    const offcanvas = bootstrap.Offcanvas.getInstance(document.getElementById('detailPanel'));
                    if (offcanvas) offcanvas.hide();

                    // Wait for panel to close then show edit modal
                    setTimeout(() => {
                        this.createEditModal(data.link);
                    }, 300);
                } else {
                    showToast(data.error || 'Error cargando datos del link', 'error');
                }
            })
            .catch(error => {
                showToast('Error cargando datos del link', 'error');
            });
    },

    // Create edit modal
    createEditModal: function(linkData) {
        console.log('📝 Creating edit modal with data:', linkData);

        // Remove existing modal if any
        const existingModal = document.getElementById('editLinkModal');
        if (existingModal) {
            document.body.removeChild(existingModal);
        }

        // Helper para escapar HTML
        const escapeHtml = (text) => {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        };

        // Calcular info de vigencia
        const expiresAt = new Date(linkData.expires_at);
        const now = new Date();
        const timeLeft = expiresAt - now;
        const daysLeft = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
        const hoursLeft = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

        let timeLeftText = '';
        let badgeClass = 'bg-success';

        if (daysLeft > 3) {
            timeLeftText = `Quedan ${daysLeft} días`;
            badgeClass = 'bg-success';
        } else if (daysLeft >= 1) {
            timeLeftText = `Quedan ${daysLeft} día${daysLeft > 1 ? 's' : ''}`;
            badgeClass = 'bg-warning text-dark';
        } else if (hoursLeft > 0) {
            timeLeftText = `Quedan ${hoursLeft} horas`;
            badgeClass = 'bg-danger';
        } else {
            timeLeftText = 'Expirado';
            badgeClass = 'bg-secondary';
        }

        const expiresFormatted = expiresAt.toLocaleDateString('es-MX', {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        const createdAt = new Date(linkData.created_at);
        const createdFormatted = createdAt.toLocaleDateString('es-MX', {
            day: 'numeric',
            month: 'short',
            year: 'numeric'
        });

        const statusDisplay = linkData.status === 'active' ? 'Activo' :
                             linkData.status === 'paid' ? 'Pagado' :
                             linkData.status === 'expired' ? 'Expirado' :
                             linkData.status === 'cancelled' ? 'Cancelado' :
                             linkData.status || 'Desconocido';

        const statusBadge = linkData.status === 'active' ? 'bg-success' :
                           linkData.status === 'paid' ? 'bg-primary' :
                           linkData.status === 'expired' ? 'bg-secondary' :
                           linkData.status === 'cancelled' ? 'bg-danger' :
                           'bg-secondary';

        console.log('📊 Link status info:', {
            status: linkData.status,
            statusDisplay,
            statusBadge,
            token: linkData.token,
            created_at: linkData.created_at
        });

        // Create edit modal dynamically
        const editModal = document.createElement('div');
        editModal.className = 'modal fade';
        editModal.id = 'editLinkModal';
        editModal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <div class="w-100">
                            <h5 class="modal-title">
                                <i class="iconoir-edit-pencil me-2"></i>
                                Editar Link de Pago
                            </h5>
                            <div class="d-flex gap-3 flex-wrap mt-2">
                                <small class="text-muted">
                                    <strong>Token:</strong> <code style="font-size: 0.8rem;">${linkData.token}</code>
                                </small>
                                <small class="d-flex align-items-center gap-2">
                                    <span class="text-muted"><strong>Estado:</strong></span>
                                    <span class="badge ${statusBadge}">${statusDisplay}</span>
                                </small>
                                <small class="text-muted">
                                    <strong>Creado:</strong> ${createdFormatted}
                                </small>
                            </div>
                        </div>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="editLinkForm" novalidate>
                            <input type="hidden" name="link_id" value="${linkData.id}">

                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="edit-title" class="form-label">
                                            Título/Concepto <span class="text-danger">*</span>
                                        </label>
                                        <input type="text"
                                               class="form-control"
                                               id="edit-title"
                                               name="title"
                                               value="${escapeHtml(linkData.title)}"
                                               required
                                               minlength="3"
                                               maxlength="255"
                                               autofocus
                                               placeholder="Ej: Factura #001 - Consultoría Web"
                                               aria-required="true"
                                               aria-invalid="false"
                                               aria-describedby="edit-title-error edit-title-help">
                                        <div id="edit-title-error" class="invalid-feedback" role="alert"></div>
                                        <small id="edit-title-help" class="form-text text-muted">
                                            Será visible en el link de pago
                                        </small>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="edit-amount" class="form-label">
                                            Monto <span class="text-danger">*</span>
                                        </label>
                                        <div class="input-group">
                                            <span class="input-group-text">$</span>
                                            <input type="number"
                                                   class="form-control"
                                                   id="edit-amount"
                                                   name="amount"
                                                   value="${linkData.amount}"
                                                   step="0.01"
                                                   min="1"
                                                   max="999999"
                                                   required
                                                   placeholder="0.00"
                                                   aria-required="true"
                                                   aria-invalid="false"
                                                   aria-describedby="edit-amount-error edit-amount-help">
                                            <span class="input-group-text">MXN</span>
                                        </div>
                                        <div id="edit-amount-error" class="invalid-feedback" role="alert"></div>
                                        <small id="edit-amount-help" class="form-text text-muted">
                                            Mínimo $1, máximo $999,999 MXN
                                        </small>
                                    </div>
                                </div>
                            </div>

                            <div class="mb-3">
                                <label for="edit-description" class="form-label">
                                    Descripción <span class="text-muted small">(opcional)</span>
                                </label>
                                <textarea class="form-control"
                                          id="edit-description"
                                          name="description"
                                          rows="2"
                                          maxlength="500"
                                          placeholder="Descripción opcional del servicio o producto"
                                          aria-describedby="edit-description-count">${escapeHtml(linkData.description || '')}</textarea>
                                <small id="edit-description-count" class="form-text text-muted">
                                    <span id="editDescriptionCount">${(linkData.description || '').length}</span>/500 caracteres
                                </small>
                            </div>

                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="edit-customer-name" class="form-label">
                                            Nombre del cliente <span class="text-muted small">(opcional)</span>
                                        </label>
                                        <input type="text"
                                               class="form-control"
                                               id="edit-customer-name"
                                               name="customer_name"
                                               value="${escapeHtml(linkData.customer_name || '')}"
                                               maxlength="255"
                                               placeholder="Nombre completo"
                                               aria-invalid="false"
                                               aria-describedby="edit-customer-name-error">
                                        <div id="edit-customer-name-error" class="invalid-feedback" role="alert"></div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="edit-customer-email" class="form-label d-flex align-items-center gap-2">
                                            <i class="iconoir-mail text-muted"></i>
                                            Email del cliente
                                        </label>
                                        ${linkData.customer_email ? `
                                            <div class="alert alert-light border d-flex align-items-start gap-2 mb-0">
                                                <i class="iconoir-lock text-muted" style="margin-top: 2px;"></i>
                                                <div class="flex-grow-1">
                                                    <strong>${escapeHtml(linkData.customer_email)}</strong>
                                                    <p class="mb-0 small text-muted mt-1">
                                                        No editable (afecta notificaciones configuradas)
                                                    </p>
                                                </div>
                                            </div>
                                        ` : `
                                            <div class="alert alert-warning border d-flex align-items-start gap-2 mb-0">
                                                <i class="iconoir-warning-triangle text-warning" style="margin-top: 2px;"></i>
                                                <div class="flex-grow-1">
                                                    <strong>Sin email configurado</strong>
                                                    <p class="mb-0 small text-muted mt-1">
                                                        No se pueden enviar notificaciones. Para agregar email, crea un nuevo link.
                                                    </p>
                                                </div>
                                            </div>
                                        `}
                                    </div>
                                </div>
                            </div>

                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label class="form-label d-flex align-items-center gap-2">
                                            <i class="iconoir-calendar text-muted"></i>
                                            Vigencia del Link
                                        </label>
                                        <div class="alert alert-light border d-flex align-items-start gap-2 mb-0">
                                            <i class="iconoir-info-circle text-info" style="margin-top: 2px;"></i>
                                            <div class="flex-grow-1">
                                                <div>
                                                    <strong>Expira:</strong> ${expiresFormatted}
                                                </div>
                                                <span class="badge ${badgeClass} mt-1">${timeLeftText}</span>
                                                <p class="mb-0 small text-muted mt-2">
                                                    Para cambiar la vigencia, crea un nuevo link
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <div class="form-check mt-4">
                                            <input class="form-check-input"
                                                   type="checkbox"
                                                   id="edit-requires-invoice"
                                                   name="requires_invoice"
                                                   aria-describedby="edit-requires-invoice-help"
                                                   ${linkData.requires_invoice ? 'checked' : ''}>
                                            <label class="form-check-label" for="edit-requires-invoice">
                                                <strong>Permitir facturar</strong>
                                            </label>
                                            <div id="edit-requires-invoice-help" class="form-text">
                                                El cliente podrá generar su CFDI 4.0
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <div class="d-flex justify-content-between w-100">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                Cancelar
                            </button>
                            <button type="submit" class="btn btn-primary" id="editLinkSubmitBtn" form="editLinkForm">
                                <span class="btn-content">
                                    <i class="iconoir-check me-2"></i>
                                    Guardar Cambios
                                </span>
                                <span class="btn-loading d-none">
                                    <span class="spinner-border spinner-border-sm me-2"></span>
                                    Guardando...
                                </span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(editModal);
        const modal = new bootstrap.Modal(editModal);
        modal.show();

        // ✅ Initialize contador de caracteres
        const descriptionTextarea = editModal.querySelector('#edit-description');
        if (descriptionTextarea) {
            descriptionTextarea.addEventListener('input', function(e) {
                const count = e.target.value.length;
                const counter = editModal.querySelector('#editDescriptionCount');
                if (counter) {
                    counter.textContent = count;

                    // Limitar a 500
                    if (count > 500) {
                        e.target.value = e.target.value.substring(0, 500);
                        counter.textContent = 500;
                    }
                }
            });
        }

        // ✅ Initialize form submit handler
        const form = editModal.querySelector('#editLinkForm');
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Submitting edit form');

            const formData = new FormData(this);
            const data = Object.fromEntries(formData.entries());
            data.requires_invoice = this.querySelector('[name="requires_invoice"]').checked;

            console.log('Form data:', data);

            // ✅ Usar nueva estructura de botón con loading state
            const submitBtn = editModal.querySelector('#editLinkSubmitBtn');
            const btnContent = submitBtn.querySelector('.btn-content');
            const btnLoading = submitBtn.querySelector('.btn-loading');

            if (btnContent) btnContent.classList.add('d-none');
            if (btnLoading) btnLoading.classList.remove('d-none');
            submitBtn.disabled = true;

            fetch('/enlaces/editar/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': KitaLinkActions.getCsrfToken()
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast('Link actualizado exitosamente', 'success');
                    modal.hide();

                    // Refresh dashboard if on dashboard page
                    if (typeof updateDashboardCounts === 'function') {
                        updateDashboardCounts();
                    }
                } else {
                    showToast(data.error || 'Error actualizando link', 'error');
                }
            })
            .catch(error => {
                console.error('Edit fetch error:', error);
                showToast('Error de conexión', 'error');
            })
            .finally(() => {
                // ✅ Restaurar estado del botón
                if (btnContent) btnContent.classList.remove('d-none');
                if (btnLoading) btnLoading.classList.add('d-none');
                submitBtn.disabled = false;
            });
        });

        // Remove modal from DOM when hidden
        editModal.addEventListener('hidden.bs.modal', function() {
            if (document.body.contains(editModal)) {
                document.body.removeChild(editModal);
            }
        });
    },

    // ⚠️ DEPRECATED - No usar (el modal maneja validación internamente)
    // Initialize edit link validation (same as create link)
    initEditLinkValidation: function() {
        console.warn('⚠️ DEPRECATED: initEditLinkValidation() - El modal maneja validación internamente');
        // El código después del return está comentado para evitar warnings
        /*
        const form = document.getElementById('editLinkForm');
        if (!form) {
            console.error('❌ editLinkForm not found');
            return;
        }

        console.log('✅ Edit link validation initializing...');

        const ValidationHelpers = {
            setValid(input) {
                input.classList.add('is-valid');
                input.classList.remove('is-invalid');
                const feedback = input.parentElement.querySelector('.invalid-feedback') ||
                                 input.closest('.mb-3').querySelector('.invalid-feedback');
                if (feedback) feedback.textContent = '';
            },

            setInvalid(input, message) {
                input.classList.add('is-invalid');
                input.classList.remove('is-valid');
                const feedback = input.parentElement.querySelector('.invalid-feedback') ||
                                 input.closest('.mb-3').querySelector('.invalid-feedback');
                if (feedback) {
                    feedback.textContent = message;
                    feedback.style.display = 'block';
                }
            },

            clearValidation(input) {
                input.classList.remove('is-valid', 'is-invalid');
                const feedback = input.parentElement.querySelector('.invalid-feedback') ||
                                 input.closest('.mb-3').querySelector('.invalid-feedback');
                if (feedback) {
                    feedback.textContent = '';
                    feedback.style.display = 'none';
                }
            }
        };

        // Título
        const titleInput = form.querySelector('[name="title"]');
        if (titleInput) {
            titleInput.addEventListener('blur', function() {
                const value = this.value.trim();
                if (!value) {
                    ValidationHelpers.setInvalid(this, 'Título es requerido');
                } else if (value.length < 3) {
                    ValidationHelpers.setInvalid(this, 'Título debe tener al menos 3 caracteres');
                } else if (value.length > 255) {
                    ValidationHelpers.setInvalid(this, 'Título no puede exceder 255 caracteres');
                } else {
                    ValidationHelpers.setValid(this);
                }
            });
            titleInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) ValidationHelpers.clearValidation(this);
            });
        }

        // Monto - readonly, no validar (ya tiene .is-valid en HTML)

        // Email del cliente
        const emailInput = form.querySelector('[name="customer_email"]');
        if (emailInput) {
            emailInput.addEventListener('blur', function() {
                const value = this.value.trim();
                if (value) {
                    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                        ValidationHelpers.setInvalid(this, 'Formato de email inválido');
                    } else if (value.length > 254) {
                        ValidationHelpers.setInvalid(this, 'Email no puede exceder 254 caracteres');
                    } else {
                        ValidationHelpers.setValid(this);
                    }
                } else {
                    ValidationHelpers.clearValidation(this);
                }
            });
            emailInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) ValidationHelpers.clearValidation(this);
                this.value = this.value.toLowerCase();
            });
        }

        // Descripción con contador
        const descriptionInput = form.querySelector('[name="description"]');
        const descriptionCount = document.getElementById('editDescriptionCount');
        if (descriptionInput && descriptionCount) {
            // Inicializar contador
            descriptionCount.textContent = descriptionInput.value.length;

            descriptionInput.addEventListener('input', function() {
                const length = this.value.length;
                descriptionCount.textContent = length;
                if (length > 500) {
                    this.value = this.value.substring(0, 500);
                    descriptionCount.textContent = 500;
                }
            });
        }

        // Nombre del cliente
        const nameInput = form.querySelector('[name="customer_name"]');
        if (nameInput) {
            nameInput.addEventListener('blur', function() {
                const value = this.value.trim();
                if (value && value.length > 255) {
                    ValidationHelpers.setInvalid(this, 'Nombre no puede exceder 255 caracteres');
                } else if (value) {
                    ValidationHelpers.setValid(this);
                } else {
                    ValidationHelpers.clearValidation(this);
                }
            });
            nameInput.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) ValidationHelpers.clearValidation(this);
            });
        }

        console.log('✅ Edit link validation initialized');
        */
    },

    // ⚠️ DEPRECATED - No usar (el modal maneja submit internamente)
    // Submit edit link
    submitEditLink: function() {
        console.warn('⚠️ DEPRECATED: submitEditLink() - El modal maneja submit internamente');
        /*
        const form = document.getElementById('editLinkForm');

        // Validar HTML5 constraints primero
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        const submitBtn = document.getElementById('submitEditBtn');
        if (!submitBtn) return;

        const btnContent = submitBtn.querySelector('.btn-content');
        const btnLoading = submitBtn.querySelector('.btn-loading');

        if (btnContent) btnContent.classList.add('d-none');
        if (btnLoading) btnLoading.classList.remove('d-none');
        submitBtn.disabled = true;

        // Timeout 10 segundos
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        fetch('/enlaces/editar/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify(data),
            signal: controller.signal
        })
        .then(response => {
            clearTimeout(timeoutId);
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showToast('Link actualizado exitosamente', 'success');
                const modal = bootstrap.Modal.getInstance(document.getElementById('editLinkModal'));
                modal.hide();
                this.updateRelatedData();
            } else {
                showToast(data.error || 'Error actualizando link', 'error');
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                showToast('⏱️ Operación interrumpida (timeout 10s). Intenta de nuevo.', 'error');
            } else {
                showToast('Error de conexión. Verifica tu internet.', 'error');
            }
        })
        .finally(() => {
            if (btnContent) btnContent.classList.remove('d-none');
            if (btnLoading) btnLoading.classList.add('d-none');
            submitBtn.disabled = false;
        });
        */
    },

    // Refresh link metrics in detail panel
    refreshLinkMetrics: function(linkId) {
        const btn = event.target.closest('button');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="iconoir-refresh fa-spin"></i>';
        btn.disabled = true;

        // Reload detail panel
        this.showDetailPanel('link', linkId);

        setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.disabled = false;
            showToast('Métricas actualizadas', 'success');
        }, 1000);
    },

    // Show QR code for link
    showLinkQR: function(token, title) {
        const qrUrl = `${window.location.origin}/hola/${token}/`;

        // Create QR modal
        const qrModal = document.createElement('div');
        qrModal.className = 'modal fade';
        qrModal.id = 'qrModal';
        qrModal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="iconoir-qr-code me-2"></i>
                            QR del Link de Pago
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <h6 class="mb-3">${title}</h6>
                        <div id="qrcode" class="mb-3"></div>
                        <p class="text-muted small mb-0">Escanea para abrir el link de pago</p>
                        <code class="small">${qrUrl}</code>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cerrar</button>
                        <button type="button" class="btn btn-primary" onclick="window.print()">
                            <i class="iconoir-printer me-2"></i>
                            Imprimir
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(qrModal);
        const modal = new bootstrap.Modal(qrModal);
        modal.show();

        // Generate QR code using qrcodejs library
        setTimeout(() => {
            const qrContainer = document.getElementById('qrcode');
            if (qrContainer && typeof QRCode !== 'undefined') {
                // Clear container
                qrContainer.innerHTML = '';

                // Generate QR
                new QRCode(qrContainer, {
                    text: qrUrl,
                    width: 300,
                    height: 300,
                    colorDark: '#111827',
                    colorLight: '#ffffff',
                    correctLevel: QRCode.CorrectLevel.H
                });
            }
        }, 100);

        // Remove modal when hidden
        qrModal.addEventListener('hidden.bs.modal', function() {
            document.body.removeChild(qrModal);
        });

        // Analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'qr_code_viewed', {
                'event_category': 'payment_links',
                'event_label': 'show_qr'
            });
        }
    },

    // Update related data (dashboard counts, tables, etc.)
    updateRelatedData: function() {
        // Update dashboard counts if on dashboard
        if (window.kitaSidebar && window.kitaSidebar.updateCounts) {
            window.kitaSidebar.updateCounts();
        }

        // Update DataTable if on links page
        if (window.linksTable && window.linksTable.ajax) {
            window.linksTable.ajax.reload();
        }

        // Update dashboard analytics if charts exist
        if (window.kitaCharts && window.kitaCharts.updateAllCharts) {
            window.kitaCharts.updateAllCharts();
        }

        // Update dashboard stats cards if on dashboard
        this.updateDashboardStats();

        // Immediately refresh dashboard if on dashboard page
        if (window.location.pathname.startsWith('/panel')) {  // 🇪🇸 Migrado
            // Trigger the existing dashboard refresh mechanism
            const startDate = document.getElementById('start_date')?.value;
            const endDate = document.getElementById('end_date')?.value;

            if (startDate && endDate) {
                setTimeout(() => {
                    updateDashboardWithNewDates(startDate, endDate);
                }, 500);
            }
        }
    },

    // Update dashboard stats cards with current filters
    updateDashboardStats: function() {
        const startDate = document.getElementById('start_date')?.value;
        const endDate = document.getElementById('end_date')?.value;

        if (!startDate || !endDate) return;

        const params = new URLSearchParams({
            start_date: startDate,
            end_date: endDate
        });

        fetch(`/panel/?${params}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.analytics) {
                const analytics = data.analytics;

                // Update revenue card
                const revenueElement = document.querySelector('[data-metric="total_revenue"]');
                if (revenueElement) {
                    revenueElement.textContent = `$${analytics.total_revenue.toFixed(2)} MXN`;
                }

                // Update links card
                const linksElement = document.querySelector('[data-metric="total_links"]');
                if (linksElement) {
                    linksElement.textContent = analytics.total_links;
                }

                // Update other metrics
                const paymentsElement = document.querySelector('[data-metric="successful_payments"]');
                if (paymentsElement) {
                    paymentsElement.textContent = analytics.successful_payments;
                }

                const invoicesElement = document.querySelector('[data-metric="invoices_generated"]');
                if (invoicesElement) {
                    invoicesElement.textContent = analytics.invoices_generated;
                }
            }
        })
        .catch(error => {
            console.error('Error updating dashboard stats:', error);
        });
    },

    // Get CSRF token
    getCsrfToken: function() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) return csrfInput.value;

        const csrfCookie = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='));
        if (csrfCookie) return csrfCookie.split('=')[1];

        return '';
    }
};

// Override existing showDetailPanel to use centralized version
window.showDetailPanel = KitaLinkActions.showDetailPanel.bind(KitaLinkActions);
window.duplicateLink = KitaLinkActions.duplicateLink.bind(KitaLinkActions);
window.cancelLink = KitaLinkActions.cancelLink.bind(KitaLinkActions);
window.sendReminder = KitaLinkActions.sendReminder.bind(KitaLinkActions);
window.showEditLinkModal = KitaLinkActions.showEditLinkModal.bind(KitaLinkActions);
window.copyPublicUrl = KitaLinkActions.copyPublicUrl.bind(KitaLinkActions);
window.initLinkViewsChart = KitaLinkActions.initViewsTimeline.bind(KitaLinkActions);
window.refreshLinkMetrics = KitaLinkActions.refreshLinkMetrics.bind(KitaLinkActions);
window.showLinkQR = KitaLinkActions.showLinkQR.bind(KitaLinkActions);