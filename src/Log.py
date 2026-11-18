#####################################################################
# -*- coding: utf-8 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#               2009 John Stumpo                                    #
#                                                                   #
# This program is free software; you can redistribute it and/or     #
# modify it under the terms of the GNU General Public License       #
# as published by the Free Software Foundation; either version 2    #
# of the License, or (at your option) any later version.            #
#                                                                   #
# This program is distributed in the hope that it will be useful,   #
# but WITHOUT ANY WARRANTY; without even the implied warranty of    #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the     #
# GNU General Public License for more details.                      #
#                                                                   #
# You should have received a copy of the GNU General Public License #
# along with this program; if not, write to the Free Software       #
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,        #
# MA  02110-1301, USA.                                              #
#####################################################################

##@package Log
# Functions for various types of logging that FoFiX needs to do.

import sys
import os
import Resource
import Version
import traceback
import time
import warnings

## Whether to output log entries to stdout in addition to the logfile.
quiet = True

## Character encoding to use for logging.
encoding = "iso-8859-1"

## File object representing the logfile.
try:
  if os.name == "posix": # evilynux - logfile in ~/.fofix/ for GNU/Linux and MacOS X
    # evilynux - Under MacOS X, put the logs in ~/Library/Logs
    if os.uname()[0] == "Darwin":
      log_dir = os.path.expanduser("~/Library/Logs")
      os.makedirs(log_dir, exist_ok=True)
      logFile = open(os.path.join(log_dir, Version.appName() + ".log"), "w", encoding=encoding, errors="replace")
    else: # GNU/Linux et al.
      log_dir = Resource.getWritableResourcePath()
      os.makedirs(log_dir, exist_ok=True)
      logFile = open(os.path.join(log_dir, Version.appName() + ".log"), "w", encoding=encoding, errors="replace")
  else:
    logFile = open(Version.appName() + ".log", "w", encoding=encoding, errors="replace")  #MFH - local logfile!
except Exception:
  logFile = sys.stderr

if "-v" in sys.argv or "--verbose" in sys.argv:
  quiet = False

## Labels for different priorities, as output to the logfile.
labels = {
  "warn":   "(W)",
  "debug":  "(D)",
  "notice": "(N)",
  "error":  "(E)",
}

## Labels for different priorities, as output to stdout.
if os.name == "posix":
  displaylabels = {
    "warn":   "\033[1;33m(W)\033[0m",
    "debug":  "\033[1;34m(D)\033[0m",
    "notice": "\033[1;32m(N)\033[0m",
    "error":  "\033[1;31m(E)\033[0m",
  }
else:
  displaylabels = labels

## Generic logging function.
# @param cls    Priority class for the message
# @param msg    Log message text
def _log(cls, msg):
  if isinstance(msg, bytes):
    msg = msg.decode(encoding, "replace")
  elif not isinstance(msg, str):
    msg = str(msg)
  timeprefix = "[%12.6f] " % (time.time() - _initTime)
  if not quiet:
    print(timeprefix + displaylabels[cls] + " " + msg)
  print(timeprefix + labels[cls] + " " + msg, file=logFile)
  logFile.flush()  #stump: truncated logfiles be gone!

## Log a major error.
# If this is called while handling an exception, the traceback will
# be automatically included in the log.
# @param msg    Error message text
def error(msg):
  if sys.exc_info() == (None, None, None):
    #warnings.warn("Log.error() called without an active exception", UserWarning, 2)  #stump: should we enforce this?
    _log("error", msg)
  else:
    _log("error", msg + "\n" + traceback.format_exc())

## Log a warning.
# @param msg    Warning message text
def warn(msg):
  _log("warn", msg)

## Log a notice.
# @param msg    Notice message text
def notice(msg):
  _log("notice", msg)

## Log a debug message.
# @param msg    Debug message text
def debug(msg):
  _log("debug", msg)

## A hook to catch Python warnings.
def _showwarning(message, category, filename, lineno, file=None, line=None):
  warn("A Python warning was issued:\n" + warnings.formatwarning(message, category, filename, lineno, line))
  if _old_showwarning:
    _old_showwarning(message, category, filename, lineno, file, line)
_old_showwarning = warnings.showwarning
warnings.showwarning = _showwarning

_initTime = time.time()
debug("Logging initialized: " + time.asctime())
