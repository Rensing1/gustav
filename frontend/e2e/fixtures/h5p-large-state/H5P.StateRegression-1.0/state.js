/* A real H5P interaction whose text state can exceed the Beacon budget. */
H5P.StateRegression = function (_params, _id, data) {
  var answer = data && data.previousState ? data.previousState.answer || '' : '';
  this.attach = function (container) {
    var label = H5P.jQuery('<label>Ausführliche Antwort</label>');
    H5P.jQuery('<textarea rows="8"></textarea>').val(answer).on('input', function () {
      answer = this.value;
    }).appendTo(label);
    container.addClass('h5p-state-regression').append(label);
  };
  this.getCurrentState = function () { return { answer: answer }; };
};
