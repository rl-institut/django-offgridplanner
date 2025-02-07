/*jshint esversion: 6 */
    function submitModalForm(event, modalId=""){
        const submitFormBtn = document.getElementById(modalId + "SubmitBtn");
        submitFormBtn.click();
    }


    function showModal(event, modalId="", attrs = null){
        var modalInstance = $("#" + modalId);
        // update the attributes of the form tag of the modal
        for (const [key, value] of Object.entries(attrs)) {
            if(value){
                modalInstance.find('.modal-body form').attr(key, value);
            }
        }
         modalInstance.modal("show");
    }

    function hideModal(modalId=""){
        var modalInstance = $("#" + modalId);
         modalInstance.modal("hide");
    }
