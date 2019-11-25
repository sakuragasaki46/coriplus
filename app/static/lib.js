function checkUsername(u){
  var starts_with_period = /^\./.test(u);
  var ends_with_period = /\.$/.test(u);
  var two_periods = /\.\./.test(u);
  var forbidden_extensions = u.match(/\.(com|net|org|txt)$/);
  
  return (
    starts_with_period? 'You cannot start username with a period.':
    ends_with_period? 'You cannot end username with a period.':
    two_periods? 'You cannot have more than one period in a row.':
    forbidden_extensions? 'Your username cannot end with .' + forbidden_extensions[1]:
    'ok'
  );
}

function attachUsernameInput(){
  var usernameInputs = document.getElementsByClassName('username-input');
  for(var i=0;i<usernameInputs.length;i++)(function(usernameInput){
    var lastValue = '';
    var usernameInputMessage = document.createElement('div');
    usernameInput.oninput = function(event){
      var value = usernameInput.value;
      if (value != lastValue){
        if(!/^[a-z0-9_. ]*$/i.test(value)){
          usernameInputMessage.innerHTML = 'Usernames can only contain letters, numbers, underscores, and periods.';
          usernameInputMessage.className = 'username-input-message error';
          event.preventDefault();
          return;
        }
        if(/ /.test(value)){
          value = value.replace(/ /g,'_');
        }
        usernameInput.value = lastValue = value.toLowerCase();
        if(!value){
          usernameInputMessage.innerHTML = 'You cannot have an empty username.';
          usernameInputMessage.className = 'username-input-message error';
          return;
        }
        var message = checkUsername(value);
        if (message != 'ok'){
          usernameInputMessage.innerHTML = message;
          usernameInputMessage.className = 'username-input-message error';
          return;
        }
        usernameInputMessage.innerHTML = 'Checking username...';
        usernameInputMessage.className = 'username-input-message checking';
        requestUsernameAvailability(value, function(resp){
          if (resp.status != 'ok'){
            usernameInputMessage.innerHTML = 'Sorry, there was an unknown error.';
            usernameInputMessage.className = 'username-input-message error';
            return;
          }
          if (resp.is_available){
            usernameInputMessage.innerHTML = "The username '" + value + "' is available.";
            usernameInputMessage.className = 'username-input-message success';
            return;
          } else {
            usernameInputMessage.innerHTML = "The username '" + value + "' is not available.";
            usernameInputMessage.className = 'username-input-message error';
            return;
          }
        });
      }
    };
    usernameInputMessage.className = 'username-input-message';
    usernameInput.parentNode.appendChild(usernameInputMessage);
  })(usernameInputs[i]);
}

attachUsernameInput();

function requestUsernameAvailability(u, callback){
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/ajax/username_availability/' + u, true);
  xhr.onreadystatechange = function(){
    if (xhr.readyState == XMLHttpRequest.DONE){
      try {
        var data = JSON.parse(xhr.responseText);
        callback(data);
      } catch(ex) {
      }
    }
  }
  xhr.send();
}

function attachFileInput(){
  var fileInput = document.getElementById('fileInputContainer');
  fileInput.innerHTML = '<input type="file" accept="image/*" name="file">';
}

function showHideMessageOptions(id){
  var msgElem = document.getElementById(id);
  var options = msgElem.getElementsByClassName('message-options')[0];
  if(options.style.display == 'block'){
    options.style.display = 'none';
  } else {
    options.style.display = 'block';
  }
}

function toggleUpvote(id){
  var msgElem = document.getElementById(id);
  var upvoteLink = msgElem.getElementsByClassName('message-upvote')[0];
  var scoreCounter = msgElem.getElementsByClassName('message-score')[0];
  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/ajax/score/" + id + "/toggle", true);
  xhr.onreadystatechange = function(){
    if(xhr.readyState == XMLHttpRequest.DONE){
      if(xhr.status == 200){
        console.log('liked #' + id);
        var data = JSON.parse(xhr.responseText);
        scoreCounter.innerHTML = data.score;
      }
    }
  };
  xhr.send();
}
